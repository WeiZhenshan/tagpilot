import { test, expect } from '@playwright/test';
import fs from 'node:fs';
let thread: any, requests: any[], entries: any[];
test.beforeEach(async ({ page }) => {
  requests = [];
  entries = [{name:'fixture-analysis',display_name:'合成分析测试技能',description:'仅用于自动化测试，分析当前客群。',version:'1.0.0',category:'fact',argument_hint:'[分析目标]',user_invocable:true}];
  thread = {thread_id:'skill-fixture',title:'合成测试客群',library_id:107,status:'COMPLETED',revision:2,archived:false,pinned:false,
    plan:{revision:2,hash:'h',valid:true,plan_status:'READY',tree:{kind:'TAG_PREDICATE',clause_id:'a',tag_id:1,name:'客户余额',operator:'>',values:['0'],status:'BOUND',allowed_operators:['>'],candidates:[]}},
    count:{value:240,revision:2,plan_hash:'h'},messages:[{id:'u',role:'user',text:'圈定合成测试客群',created_at:'2026-09-30T00:00:00Z'}],versions:[],events:[],capabilities:{count:true,preview:false,create:false,insight:true}};
  await page.route('**/dev-api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if(path.endsWith('/getInfo')) return route.fulfill({json:{code:200,user:{userId:2,userName:'fixture',nickName:'合成测试'}}});
    if(path.endsWith('/library/list')) return route.fulfill({json:{code:200,rows:[{libraryId:107,libraryName:'合成测试库'}]}});
    let data: any;
    if(path.endsWith('/skills/available')) data=entries;
    else if(path.endsWith('/tags/tree')) data=[];
    else if(path.endsWith('/threads')) data=[];
    else if(path.endsWith('/runs')) { requests.push(route.request().postDataJSON());thread.messages.push({id:'a',role:'assistant',text:'合成技能运行完成',created_at:'2026-09-30T00:00:01Z'});data=thread; }
    else data=thread;
    await route.fulfill({json:{code:200,data}});
  });
});
for (const width of [1440,390]) test(`技能入口 ${width}：/ 搜索、键盘选择、客群上下文与调用`,async ({page}) => {
  await page.setViewportSize({width,height:width===390?844:960});
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-fixture');
  await expect(page.getByRole('tab',{name:'技能',exact:true})).toHaveCount(0);
  const input=page.getByRole('textbox',{name:'圈选需求或技能调用'});
  await input.fill('/');
  await expect(page.getByRole('listbox',{name:'已发布技能'})).toBeVisible();
  await expect(page.locator('.skill-menu-context')).toContainText('240 人');
  if(process.env.CAPTURE_DIR){fs.mkdirSync(process.env.CAPTURE_DIR,{recursive:true});await page.screenshot({path:`${process.env.CAPTURE_DIR}/skill-composer-${width}.png`});}
  await input.fill('/missing');await expect(page.getByText('没有匹配的技能，请调整搜索词。')).toBeVisible();
  await input.fill('/fixture');await input.press('ArrowDown');await input.press('Enter');
  await expect(page.locator('.skill-selection')).toContainText('合成分析测试技能');
  await expect(input).toHaveValue('');
  await input.fill('核对当前客群');await input.press('Enter');
  await expect(page.getByText('合成技能运行完成', {exact:true})).toBeVisible();
  expect(requests[0]).toMatchObject({skill_name:'fixture-analysis',base_revision:2,plan_hash:'h',message:'核对当前客群'});
  expect(requests[0].cohort_context).toBeUndefined();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('无技能、加载失败、取消与未统计人数',async({page})=>{
  entries=[];delete thread.count;
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-fixture');
  const input=page.getByRole('textbox',{name:'圈选需求或技能调用'});
  await input.fill('/');await expect(page.getByText('暂无已发布的可调用技能，请先到洞察技能页面登记并发布。')).toBeVisible();
  await expect(page.locator('.skill-menu-context')).toContainText('人数未统计');
  await input.press('Escape');await expect(page.locator('.skill-menu')).toHaveCount(0);
  await page.route('**/skills/available',route=>route.fulfill({json:{code:503,msg:'技能登记服务暂不可用'}}));
  await input.fill('');await input.fill('/');await expect(page.getByText('技能登记服务暂不可用')).toBeVisible();
  expect(requests).toHaveLength(0);
});

test('长技能列表保持键盘选项可见',async({page})=>{
  entries=Array.from({length:16},(_,i)=>({name:`fixture-skill-${i}`,display_name:`合成测试技能 ${i}`,description:'仅用于长列表键盘测试',version:'1.0.0',category:'general',argument_hint:'',user_invocable:true}));
  await page.setViewportSize({width:390,height:844});await page.goto('/agent-ui/?libraryId=107&threadId=skill-fixture');
  const input=page.getByRole('textbox',{name:'圈选需求或技能调用'});await input.fill('/');
  await expect(page.getByRole('option')).toHaveCount(16);
  for(let i=0;i<13;i++) await input.press('ArrowDown');
  await expect.poll(()=>page.locator('#composer-skill-13').evaluate(el=>{const item=el.getBoundingClientRect(),list=el.parentElement!.getBoundingClientRect();return {visible:item.top>=list.top&&item.bottom<=list.bottom,selected:el.getAttribute('aria-selected')}})).toEqual({visible:true,selected:'true'});
  if(process.env.CAPTURE_DIR) await page.screenshot({path:`${process.env.CAPTURE_DIR}/skill-keyboard-390.png`});
  await input.press('Escape');expect(requests).toHaveLength(0);
});

test('完整斜杠命令直接调用与未知命令反馈',async({page})=>{
 await page.goto('/agent-ui/?libraryId=107&threadId=skill-fixture');const input=page.getByRole('textbox',{name:'圈选需求或技能调用'});
 await input.fill('/unknown 分析');await page.getByRole('button',{name:'发送需求'}).click();await expect(page.getByText('未找到可调用的已发布技能，请输入 / 从列表选择。')).toBeVisible();expect(requests).toHaveLength(0);
 await input.fill('/fixture-analysis 核对当前客群');await page.getByRole('button',{name:'发送需求'}).click();await expect(page.getByText('合成技能运行完成',{exact:true})).toBeVisible();expect(requests[0]).toMatchObject({skill_name:'fixture-analysis',message:'核对当前客群'});
});
