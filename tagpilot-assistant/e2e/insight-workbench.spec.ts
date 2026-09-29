import {test,expect} from '@playwright/test';
import fs from 'node:fs';
const reportSource=JSON.parse(fs.readFileSync(new URL('./fixtures/insight-sql-report.json',import.meta.url),'utf-8'));
// 报告来自 Java 合成H2取数→Python执行器，API仍为mock；无真实客户或模型请求。
const names:Record<string,string>={asset_structure_profile:'客群资产结构透视',product_holding_gap:'产品持仓缺口诊断',opportunity_priority:'营销机会优先级排序'};
let t:any,report:any,runBodies:any[],editCalls=0;
test.beforeEach(async({page})=>{
 report=structuredClone(reportSource);runBodies=[];editCalls=0;
 t={thread_id:'sql-reference',title:'合成SQL参考客群',library_id:107,status:'COMPLETED',revision:1,archived:false,pinned:false,
  plan:{revision:1,hash:report.cohort.plan_hash,valid:true,plan_status:'READY',build_id:'sql-build',snapshot_id:'sql-snapshot',tree:{logic:'AND',children:[{clause_id:'aum',source_span:'合成SQL参考条件',tag_id:1,name:'客户AUM',operator:'>',values:['0'],status:'BOUND',allowed_operators:['>'],unit:'CNY',value_unit:'CNY',value_scale:'1',candidates:[]}]}},
  count:{value:240,revision:1,plan_hash:report.cohort.plan_hash},messages:[{id:'user',role:'user',text:'对合成客群做大额入金转化分析',created_at:'2026-09-29T10:00:00Z'}],versions:[],events:[],capabilities:{count:true,create:false,preview:false,insight:true}};
 await page.route('**/dev-api/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname,body=route.request().postDataJSON();let data:any;
  if(path.endsWith('/getInfo'))return route.fulfill({json:{code:200,user:{userId:2,userName:'fixture',nickName:'合成测试'}}});
  if(path.endsWith('/library/list'))return route.fulfill({json:{code:200,rows:[{libraryId:107,libraryName:'合成测试标签库'}]}});
  if(path.endsWith('/catalog'))data={skills:reportSource.results.map((r,i)=>({pack_hash:r.pack_hash,manifest:{id:r.skill_id,name:names[r.skill_id],layer:`L${i+1}`,question:'核验客群事实与可营销边界',preconditions:{min_sample:20,max_stale_days:2},metrics:[]}})),versions:reportSource.results.map(r=>({skill_id:r.skill_id,status:'PUBLISHED',version:'0.1.0',pack_hash:r.pack_hash}))};
  else if(path.endsWith('/tags/tree'))data=[];
  else if(path.endsWith('/threads'))data=[{threadId:t.thread_id,title:t.title,libraryId:107,archived:'0',pinned:'0'}];
  else if(path.endsWith('/route'))data={skills:['asset_structure_profile'],parameters:{asset_structure_profile:{benchmark_type:'all_customers'}},needs_confirmation:true};
  else if(path.endsWith('/run')){runBodies.push(body);data=structuredClone(report);data.results=data.results.filter((r:any)=>body.skill_ids.includes(r.skill_id));t.insight_report=data;}
  else if(path.endsWith('/edit')){editCalls++;const classification=body.utterance.includes('只看')?'data':body.utterance.includes('基准')?'definition':'view';if(classification==='view'){data={change:{classification,parameters:{}},requires_confirmation:false,report:structuredClone(t.insight_report),message:'已应用视图变化，事实保持当前快照。'};const chart=data.report.results.find((r:any)=>r.skill_id===body.skill_id).charts.find((c:any)=>c.id===body.chart_id);chart.series.forEach((s:any)=>s.points.reverse());t.insight_report=data.report;}else data={change:{classification,parameters:{}},requires_confirmation:true,report:null,message:'须确认新客群或口径后重跑，当前报告保留。'};}
  else if(path.endsWith('/feedback'))data=null;
  else if(path.endsWith('/runs')){t.revision++;t.plan.hash='changed';t.plan.revision=t.revision;delete t.count;data=t;}
  else if(path.endsWith('/events'))return route.fulfill({contentType:'text/event-stream',body:`event: state\ndata: ${JSON.stringify(t)}\n\n`});
  else data=t;
  await route.fulfill({json:{code:200,data}});
 });
});
async function open(page:any,width=1440){await page.setViewportSize({width,height:960});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/agent-ui/?libraryId=107&threadId=sql-reference');await expect(page.getByRole('button',{name:'编辑条件：客户AUM',exact:true})).toBeVisible();}

test('正式洞察桌面：技能chip、独立SQL报告、视图修改、Ask与反馈',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await open(page);
 await page.getByRole('tab',{name:'技能',exact:true}).click();await page.getByRole('button',{name:'添加大额入金转化包'}).click();
 await expect(page.getByRole('button',{name:'移除资产结构技能'})).toBeVisible();await expect(page.getByRole('button',{name:'发送需求'})).toBeEnabled();
 await page.getByRole('button',{name:'发送需求'}).click();await expect(page.getByRole('heading',{name:'合成SQL参考客群',exact:true})).toBeVisible();
 expect(runBodies[0].skill_ids).toEqual(['asset_structure_profile','product_holding_gap','opportunity_priority']);
 await expect(page.locator('.insight-summary')).toContainText('合成数据预览');await expect(page.locator('.insight-summary')).toContainText('数据日期');
 await page.getByRole('button',{name:'宽模式',exact:true}).click();await expect(page.getByRole('button',{name:'收起宽模式',exact:true})).toBeVisible();
 await expect(page.getByRole('region',{name:'总AUM',exact:true})).toContainText('120,000,000元');
 if(process.env.CAPTURE_DIR){fs.mkdirSync(process.env.CAPTURE_DIR,{recursive:true});await page.screenshot({path:`${process.env.CAPTURE_DIR}/workbench-desktop.png`,fullPage:true});}
 await page.getByRole('button',{name:'产品缺口',exact:true}).click();await expect(page.getByRole('heading',{name:'理财持仓核验',exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'修改图表'}).selectOption('coverage');await page.getByRole('textbox',{name:'改图需求'}).fill('按降序排序');await page.getByRole('button',{name:'核验并应用'}).click();await expect(page.getByText('视图变化 · 已应用视图变化，事实保持当前快照。')).toBeVisible();
 await page.getByRole('textbox',{name:'改图需求'}).fill('只看高资产客户');await page.getByRole('button',{name:'核验并应用'}).click();await expect(page.getByRole('button',{name:'保留当前报告'})).toBeVisible();await expect(page.getByRole('heading',{name:'理财持仓核验',exact:true})).toBeVisible();expect(editCalls).toBe(2);
 await page.getByRole('button',{name:'保留当前报告'}).click();await page.getByRole('textbox',{name:'洞察反馈'}).fill('合成核对：希望保留标准化口径说明');await page.getByRole('button',{name:'保存反馈'}).click();await expect(page.getByRole('status').filter({hasText:'反馈已保存'})).toBeVisible();
 expect(errors).toEqual([]);
});

test('正式洞察手机：路由确认、参数保留和版本失效',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/agent-ui/?libraryId=107&threadId=sql-reference');
 await page.getByRole('textbox').fill('分析资产结构，使用全部客户基准');await page.getByRole('button',{name:'发送需求'}).click();
 await expect(page.getByText('已添加推荐技能，请确认后发送运行。')).toBeVisible();await expect(page.getByText('资产结构 · 比较基准：全部客户')).toBeVisible();
 await page.getByRole('button',{name:'发送需求'}).click();await expect(page.getByRole('heading',{name:'合成SQL参考客群',exact:true})).toBeVisible();expect(runBodies[0].parameters).toEqual({asset_structure_profile:{benchmark_type:'all_customers'}});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 if(process.env.CAPTURE_DIR){fs.mkdirSync(process.env.CAPTURE_DIR,{recursive:true});await page.screenshot({path:`${process.env.CAPTURE_DIR}/workbench-mobile.png`,fullPage:true});}
 t.revision=2;t.plan.revision=2;t.plan.hash='changed';delete t.count;await page.reload();await page.getByRole('tab',{name:'洞察',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'已过期'}).last()).toBeVisible();await expect(page.getByRole('button',{name:'复制本段摘要'})).toBeDisabled();for(const b of await page.getByRole('button',{name:'导出 SVG',exact:true}).all())await expect(b).toBeDisabled();
});
