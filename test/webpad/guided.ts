// Guided IME test (bun + WebView2). Run from tmp/webpad:  bun guided.ts
// Each step says what to press; the page records keyboard/composition events and judges PASS/FAIL itself.
// Results are written to results.json and events.log next to this file.
import { Webview } from "webview-bun";
import { appendFileSync, writeFileSync } from "node:fs";

const dir = new URL(".", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const LOG = dir + "events.log";
const RESULTS = dir + "results.json";
writeFileSync(LOG, `# ${new Date().toISOString()} guided test started\n`);

const html = `<!doctype html><meta charset="utf-8">
<style>
  body{font:16px "Segoe UI","Microsoft JhengHei",sans-serif;margin:0;display:flex;flex-direction:column;height:100vh}
  #head{padding:10px 14px;background:#eef}
  #step{font-size:20px;font-weight:600;margin-bottom:4px}
  #hint{color:#333}
  textarea{flex:1;font:24px "Microsoft JhengHei",sans-serif;padding:10px;border:0;outline:none}
  #res{padding:8px 14px;background:#f6f6f6;white-space:pre-wrap;font:14px Consolas,monospace;max-height:30vh;overflow:auto}
  button{font:inherit;padding:4px 14px;margin-right:8px}
  .pass{color:#080}.fail{color:#c00}
</style>
<div id="head"><div id="step"></div><div id="hint"></div>
  <p><button id="done">這步做完了 →</button><button id="skip">略過</button></p></div>
<textarea id="t" autofocus></textarea>
<div id="res"></div>
<script>
let steps = [
 { title:'步驟 1：中文模式', hint:'確認 CapsLock 燈「亮」(你的設定：亮＝中文)。然後在下面按 t 再按 /（注音 ㄔㄛ→）幾下，再按 Esc 清掉。',
   expect:'compose', check:e=>e.composition>0 },
 { title:'步驟 2：切到英文', hint:'按一下 CapsLock 讓它「熄」。然後按 a b c 三個鍵。應該直接出現 abc，不會組字。',
   expect:'english', check:e=>e.composition===0 && e.inputs.includes('abc') },
 { title:'步驟 3：切回中文', hint:'再按一次 CapsLock 讓它「亮」，按 t / 6（ㄔㄥˊ）。應該又開始組字。再按 Esc。',
   expect:'compose', check:e=>e.composition>0 },
 { title:'步驟 4：Alt+Tab 來回', hint:'按 Alt+Tab 切到別的視窗，馬上再 Alt+Tab 切回來（點一下這個輸入框），然後按 t / 6。應該仍會組字。',
   expect:'compose', check:e=>e.composition>0 && e.blur>0 },
 { title:'步驟 5：英文狀態下 Alt+Tab', hint:'先按 CapsLock 讓它「熄」(英文)，Alt+Tab 出去再回來，按 a b c 應直接出現。最後把 CapsLock 開回「亮」。',
   expect:'english', check:e=>e.composition===0 && e.inputs.includes('abc') && e.blur>0 },
];
const WANT = ${JSON.stringify(Bun.env.STEPS ?? '')};
if (WANT) { const keep = WANT.split(',').map(Number); steps = steps.filter((_, n) => keep.includes(n + 1)); }
let i = 0, cur = null; const results = [];
const t = document.getElementById('t');
function fresh(){ cur = {composition:0, keys:0, inputs:'', blur:0, caps:[]}; }
function show(){
  const s = steps[i];
  document.getElementById('step').textContent = s ? s.title : '全部完成';
  document.getElementById('hint').textContent = s ? s.hint : '結果已寫入 tmp/webpad/results.json，可以關閉視窗。';
  document.getElementById('done').style.display = s ? '' : 'none';
  document.getElementById('skip').style.display = s ? '' : 'none';
  t.value=''; fresh(); t.focus();
}
function finish(skipped){
  const s = steps[i]; const ok = skipped ? null : s.check(cur);
  results.push({step:s.title, ok, skipped, ...cur});
  const line = (ok===null?'SKIP':ok?'PASS':'FAIL') + '  ' + s.title + '  composition=' + cur.composition + ' keys=' + cur.keys + ' inputs=' + JSON.stringify(cur.inputs) + ' blur=' + cur.blur;
  const div = document.createElement('div'); div.className = ok?'pass':ok===false?'fail':''; div.textContent = line;
  document.getElementById('res').appendChild(div);
  window.saveResults(JSON.stringify(results, null, 2)); window.saveLog(line);
  i++; show();
}
document.getElementById('done').onclick = () => finish(false);
document.getElementById('skip').onclick = () => finish(true);
t.addEventListener('keydown', e => { if(!cur) return; cur.keys++; cur.caps.push(e.getModifierState('CapsLock')); window.saveLog('keydown '+e.key+' '+e.code+' composing='+e.isComposing+' caps='+e.getModifierState('CapsLock')); });
t.addEventListener('compositionstart', () => { cur.composition++; window.saveLog('compositionstart'); });
t.addEventListener('compositionupdate', e => window.saveLog('compositionupdate '+e.data));
t.addEventListener('input', e => { cur.inputs += (e.inputType==='insertText' && e.data) ? e.data : ''; window.saveLog('input '+e.inputType+' '+e.data); });
window.addEventListener('blur', () => { if(cur) cur.blur++; window.saveLog('blur'); });
window.addEventListener('focus', () => window.saveLog('focus'));
show();
</script>`;

const webview = new Webview();
webview.title = "新酷音 IME 引導測試";
webview.size = { width: 900, height: 620, hint: 0 };
webview.bind("saveLog", (line: string) => appendFileSync(LOG, line + "\n"));
webview.bind("saveResults", (json: string) => writeFileSync(RESULTS, json));
webview.setHTML(html);
webview.run();
