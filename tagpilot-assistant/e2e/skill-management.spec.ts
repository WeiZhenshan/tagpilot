import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
let server: http.Server, origin: string;
const root=path.resolve('../ruoyi-ui/dist');
test.beforeAll(async()=>{
 server=http.createServer((req,res)=>{
   let file=path.join(root,decodeURIComponent(new URL(req.url!,'http://localhost').pathname));
   if(!file.startsWith(root)){res.writeHead(403).end();return;}
   if(!fs.existsSync(file)||fs.statSync(file).isDirectory()) file=path.join(root,'index.html');
   const mime:Record<string,string>={'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml','.png':'image/png','.woff':'font/woff','.woff2':'font/woff2','.ttf':'font/ttf'};
   res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(res);
 });
 await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));origin=`http://127.0.0.1:${(server.address() as any).port}`;
});
test.afterAll(async()=>{await new Promise<void>(resolve=>server.close(()=>resolve()));});
for(const width of [1440,390])test(`技能登记 ${width}：创建、保存、发布、草稿与已发布隔离`,async({page,context})=>{
 let rows:any[]=[];let calls:string[]=[];
 await context.addCookies([{name:'Admin-Token',value:'fixture-token',url:origin}]);
 await page.route('**/*api/**',async route=>{
  const p=new URL(route.request().url()).pathname, method=route.request().method();let data:any;
  if(p.endsWith('/getInfo'))return route.fulfill({json:{code:200,roles:['admin'],permissions:['*:*:*'],user:{userId:1,userName:'fixture',nickName:'合成测试',avatar:''}}});
  if(p.endsWith('/getRouters'))data=[{name:'Taglibrary',path:'/taglibrary',component:'Layout',meta:{title:'标签管理'},children:[{name:'SkillManagement',path:'insight-skill',component:'taglibrary/insight-skill/index',meta:{title:'洞察技能'}}]}];
  else if(p.endsWith('/skills')&&method==='GET')data=rows;
  else if(p.endsWith('/skills')&&method==='POST'){const body=route.request().postDataJSON();rows=[{...body,row_version:body.row_version+1,published:rows[0]?.published||null}];calls.push('save');}
  else if(p.endsWith('/publish')){rows[0].published=JSON.parse(JSON.stringify(rows[0]));delete rows[0].published.published;rows[0].row_version++;calls.push('publish');}
  else if(p.endsWith('/retire')){rows[0].published=null;rows[0].row_version++;}
  else data=[];
  await route.fulfill({json:{code:200,data}});
 });
 await page.setViewportSize({width,height:width===390?844:960});
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto(origin+'/taglibrary/insight-skill');
 await expect(page.getByText('还没有登记技能',{exact:true})).toBeVisible();
 if(process.env.CAPTURE_DIR){fs.mkdirSync(process.env.CAPTURE_DIR,{recursive:true});await page.screenshot({path:`${process.env.CAPTURE_DIR}/skill-list-${width}.png`,fullPage:true});}
 await page.getByRole('button',{name:'创建技能',exact:true}).click();
 await page.getByPlaceholder('业务可读的技能名称').fill('合成测试技能');
 await page.getByPlaceholder('例如 customer-profile').fill('fixture-analysis');
 await page.getByPlaceholder('说明这个技能能做什么',{exact:false}).fill('合成测试：分析当前客群已有事实。');
 await page.getByRole('tab',{name:'技能指令',exact:true}).click();
 await page.getByRole('textbox',{name:'技能指令',exact:true}).fill('只使用已有条件与人数。缺少指标时说明缺失。');
 await page.getByRole('tab',{name:'支持资源',exact:true}).click();
 await page.getByRole('button',{name:'添加文本资源',exact:true}).click();
 await page.getByRole('textbox',{name:'资源1路径'}).fill('references/guide.md');
 await page.getByRole('textbox',{name:'资源1内容'}).fill('测试参考资料');
 await page.getByRole('tab',{name:'SKILL.md 预览',exact:true}).click();await expect(page.locator('.skill-source')).toContainText('name: "fixture-analysis"');
 await page.waitForTimeout(350); // Element UI tabs 使用 CSS 过渡，截图等到下划线稳定。
 if(process.env.CAPTURE_DIR) await page.screenshot({path:`${process.env.CAPTURE_DIR}/skill-editor-${width}.png`,fullPage:true});
 await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 await expect(page.getByRole('button',{name:'检查并发布'})).toBeVisible();await page.getByRole('button',{name:'检查并发布'}).click();
 await expect(page.getByRole('dialog',{name:'发布技能'})).toBeVisible();
 await page.getByRole('button',{name:'确认发布',exact:true}).click();await expect(page.getByRole('dialog',{name:'发布技能'})).toBeHidden();await expect(page.getByText('已发布 v1.0.0；编辑草稿不会影响正在使用的版本。',{exact:true})).toBeVisible();
 expect(calls).toEqual(['save','publish']);
 if(process.env.CAPTURE_DIR){
  fs.mkdirSync(process.env.CAPTURE_DIR,{recursive:true});
  await expect(page.getByRole('tab',{name:'基本信息',exact:true})).toHaveAttribute('aria-selected','true');
  await page.waitForTimeout(350); // 发布后 refreshActive 切回基本信息，等待 Element tabs 过渡。
  await page.locator('.skill-header').scrollIntoViewIfNeeded();await page.screenshot({path:`${process.env.CAPTURE_DIR}/skill-management-${width}.png`,fullPage:true});
  await page.locator('.skill-reading-options').last().scrollIntoViewIfNeeded();await page.screenshot({path:`${process.env.CAPTURE_DIR}/skill-reading-${width}.png`});
 }
 await page.getByRole('button',{name:'编辑草稿',exact:true}).click();await page.getByPlaceholder('1.0.0').fill('1.1.0');
 await page.getByRole('tab',{name:'技能指令',exact:true}).click();await page.getByRole('textbox',{name:'技能指令',exact:true}).fill('待发布的合成修改');
 await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 expect(rows[0].published.instructions).toBe('只使用已有条件与人数。缺少指标时说明缺失。');
 await page.locator('label.el-radio-button').filter({hasText:'已发布 1.0.0'}).click();await page.getByRole('tab',{name:'技能指令',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'技能指令',exact:true})).toHaveValue('只使用已有条件与人数。缺少指标时说明缺失。');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
