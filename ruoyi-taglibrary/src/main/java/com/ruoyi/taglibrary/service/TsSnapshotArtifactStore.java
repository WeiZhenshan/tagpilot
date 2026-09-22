package com.ruoyi.taglibrary.service;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.net.URI;
import java.io.IOException;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** 不可变文件：先完整写临时文件再原子重命名，禁止覆盖已有快照。 */
@Component
public class TsSnapshotArtifactStore {
    @Value("${tag.snapshot-dir:./data/tag-snapshots}") private String directory = "./data/tag-snapshots";
    public void write(TsCatalogSnapshot snapshot, String jsonl) {
        Path temp = null;
        try {
            Path root = Paths.get(directory).toAbsolutePath().normalize(); Files.createDirectories(root);
            if (!snapshot.getSnapshotId().matches("[A-Za-z0-9_-]{1,40}")) throw new ServiceException("快照编号非法");
            Path target = root.resolve(snapshot.getSnapshotId() + ".jsonl");
            if (Files.exists(target)) throw new ServiceException("快照文件已存在，禁止覆盖");
            temp = Files.createTempFile(root, ".snapshot-", ".tmp");
            Files.write(temp, jsonl.getBytes(StandardCharsets.UTF_8));
            try (java.nio.channels.FileChannel channel = java.nio.channels.FileChannel.open(temp, StandardOpenOption.WRITE)) { channel.force(true); }
            Files.createLink(target, temp); // 原子创建、不覆盖；finally 删除临时链接
            snapshot.setStorageUri(target.toUri().toString());
            snapshot.setFileSha256(TsSnapshotCanonicalizer.sha256(jsonl));
        } catch (IOException e) { throw new ServiceException("快照文件写入失败"); }
        finally { if (temp != null) try { Files.deleteIfExists(temp); } catch (IOException ignored) { } }
    }
    public Path verifiedPath(TsCatalogSnapshot snapshot) {
        try {
            Path root = Paths.get(directory).toRealPath();
            Path file;
            try {
                file = Paths.get(URI.create(snapshot.getStorageUri())).toRealPath();
            } catch (Exception e) {
                // 目录搬迁后 DB storage_uri 可能仍指向旧绝对路径；只允许回落到当前 snapshot-dir 下同名文件。
                Path relocated = root.resolve(snapshot.getSnapshotId() + ".jsonl");
                if (!Files.isRegularFile(relocated)) throw e;
                file = relocated.toRealPath();
            }
            if (!file.startsWith(root) || !Files.isRegularFile(file)) throw new IOException();
            String content = new String(Files.readAllBytes(file), StandardCharsets.UTF_8);
            if (!TsSnapshotCanonicalizer.sha256(content).equals(snapshot.getFileSha256())) throw new IOException();
            return file;
        } catch (Exception e) { throw new ServiceException("快照文件缺失或校验失败"); }
    }
}
