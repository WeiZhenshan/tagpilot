"""每 build 独立 Collection，显式过滤，故障直接向调用方报告。"""
import hashlib
import json
import os
import re
from tag_semantic.index.store import IndexStore


class MilvusUnavailable(RuntimeError):
    pass


def id_hash(ids):
    return hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()


class MilvusStore(IndexStore):
    store_type = 'MILVUS'

    def __init__(self, uri=None, collection=None, library_id=None, embedder=None, client=None):
        self.collection = collection
        self.library_id = library_id
        self.embedder = embedder
        self.docs = []
        self._client = client
        self.uri = uri or os.getenv('MILVUS_URI', 'http://127.0.0.1:19530')

    @property
    def client(self):
        if self._client is None:
            try:
                from pymilvus import MilvusClient
                self._client = MilvusClient(uri=self.uri, token=os.getenv('MILVUS_TOKEN', ''), timeout=10)
            except Exception as exc:
                raise MilvusUnavailable('Milvus 连接失败，未降级') from exc
        return self._client

    def build(self, docs):
        if not docs or not self.collection or not re.fullmatch(r'tag_docs_[a-zA-Z0-9_]{1,80}', self.collection):
            raise MilvusUnavailable('需要非空文档与独立 Collection 名称')
        from pymilvus import DataType, Function, FunctionType
        if self.client.has_collection(self.collection):
            raise ValueError('Collection 已存在，禁止覆盖')
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        for name, length in [('doc_id', 512), ('doc_type', 16), ('concept_id', 128), ('family_key', 768), ('code', 256)]:
            schema.add_field(name, DataType.VARCHAR, max_length=length, is_primary=name == 'doc_id')
        schema.add_field('library_id', DataType.INT64)
        schema.add_field('tag_id', DataType.INT64)
        for name, size in [('name_text', 4096), ('body_text', 32768)]:
            schema.add_field(name, DataType.VARCHAR, max_length=size, enable_analyzer=True,
                             analyzer_params={'tokenizer': {'type': 'jieba'}})
        for name in ('name', 'body'):
            schema.add_field('sparse_' + name, DataType.SPARSE_FLOAT_VECTOR)
            schema.add_function(Function(name='bm25_' + name, input_field_names=[name + '_text'],
                                         output_field_names=['sparse_' + name], function_type=FunctionType.BM25))
        schema.add_field('dense', DataType.FLOAT_VECTOR, dim=len(docs[0]['dense']))
        params = self.client.prepare_index_params()
        params.add_index(field_name='dense', index_type='FLAT', metric_type='COSINE')
        for name in ('sparse_name', 'sparse_body'):
            params.add_index(field_name=name, index_type='SPARSE_INVERTED_INDEX', metric_type='BM25')
        for name in ('tag_id', 'concept_id', 'doc_type', 'library_id'):
            params.add_index(field_name=name, index_type='INVERTED')
        self.client.create_collection(collection_name=self.collection, schema=schema, index_params=params, consistency_level='Strong')
        self.docs = docs
        records = []
        for doc in docs:
            row = {k: str(doc.get(k) or '') for k in ('doc_id', 'doc_type', 'concept_id', 'family_key', 'code', 'name_text', 'body_text')}
            row.update(library_id=int(self.library_id), tag_id=int(doc.get('tag_id') or -1), dense=doc['dense'])
            records.append(row)
        for offset in range(0, len(records), 200):
            self.client.insert(collection_name=self.collection, data=records[offset:offset + 200])
        self.client.flush(collection_name=self.collection)
        self.client.load_collection(collection_name=self.collection)
        stats = self.stats()
        if stats['doc_id_hash'] != id_hash(d['doc_id'] for d in docs):
            raise ValueError('Milvus 回读行集不一致')
        return stats

    def _filter(self, filters):
        tags = filters.get('eligible_tag_ids')
        concepts = filters.get('eligible_concept_ids')
        if tags is None or concepts is None:
            raise ValueError('Milvus 请求必须显式提供标签及概念白名单')
        if not tags:
            return None
        tag_expr = 'tag_id in ' + json.dumps(sorted(int(x) for x in tags))
        concept_expr = 'concept_id in ' + json.dumps(sorted(str(x) for x in concepts)) if concepts else 'tag_id == -999999999'
        return f'library_id == {int(self.library_id)} and ((doc_type != "concept" and {tag_expr}) or (doc_type == "concept" and {concept_expr}))'

    def search(self, channel, query, filters, k):
        expression = self._filter(filters)
        if expression is None:
            return []
        dense = channel == 'dense'
        field = 'dense' if dense else {'bm25_name': 'sparse_name', 'bm25_body': 'sparse_body'}[channel]
        data = self.embedder.encode([query]) if dense else [query]
        results = self.client.search(collection_name=self.collection, data=data, anns_field=field,
                                     filter=expression, limit=k, output_fields=['doc_id'],
                                     search_params={'metric_type': 'COSINE' if dense else 'BM25'}, consistency_level='Strong')
        by_id = {d['doc_id']: d for d in self.docs}
        hits = []
        for hit in results[0]:
            doc = by_id.get(hit.get('doc_id') or hit.get('id') or hit.get('entity', {}).get('doc_id'))
            if doc is None:
                raise ValueError('Milvus 返回了 manifest 外文档')
            hits.append({'doc': doc, 'score': float(hit['distance']), 'rank': len(hits) + 1, 'channel': channel})
        return hits

    def stats(self):
        ids = []
        iterator = self.client.query_iterator(collection_name=self.collection, batch_size=1000, output_fields=['doc_id'], filter='')
        try:
            while True:
                batch = iterator.next()
                if not batch:
                    break
                ids.extend(row['doc_id'] for row in batch)
        finally:
            iterator.close()
        return {'store_type': 'MILVUS', 'milvus_collection': self.collection, 'doc_count': len(ids),
                'doc_id_hash': id_hash(ids), 'load_state': str(self.client.get_load_state(self.collection)),
                'aliases': self.client.list_aliases(self.collection).get('aliases', [])}

    def activate(self, build_id):
        alias = f'tag_docs_active_l{int(self.library_id)}'
        aliases = self.client.list_aliases().get('aliases', [])
        if alias in aliases:
            self.client.alter_alias(collection_name=self.collection, alias=alias)
        else:
            self.client.create_alias(collection_name=self.collection, alias=alias)

    def drop(self, build_id):
        if self.client.list_aliases(self.collection).get('aliases'):
            raise ValueError('仍被 alias 使用，拒绝清理')
        self.client.drop_collection(self.collection)

    def deactivate(self):
        """只移除仍指向本构建的 alias；不删除 Collection，不影响其他激活者。"""
        alias = f'tag_docs_active_l{int(self.library_id)}'
        if alias in self.client.list_aliases(self.collection).get('aliases', []):
            self.client.drop_alias(alias=alias)
            return True
        return False
