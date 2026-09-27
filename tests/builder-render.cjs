const { JSDOM } = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'templates/builder.html'), 'utf8'), {runScripts:'outside-only', pretendToBeVisual:true});
  const w = dom.window;
  w.document.addEventListener = () => {};
  const pending = [];
  let calls = 0;
  let purges = 0;
  w.Plotly = {
    react: (plot, traces, layout) => {
      assert.equal(plot.isConnected, true, 'Plotly must receive a mounted card');
      assert.ok(layout.height >= 100);
      plot.classList.add('js-plotly-plot');
      calls++;
      return new Promise(resolve => pending.push(resolve));
    },
    purge: () => { assert.equal(pending.length, 0, 'must not purge a pending render'); purges++; },
  };
  w.eval(fs.readFileSync(path.join(root, 'static/js/builder-model.js'), 'utf8'));
  w.eval(fs.readFileSync(path.join(root, 'static/js/builder.js'), 'utf8') + `
    cacheBuilderElements();
    builderState.dataset = {id:'test',columns:['Region'],column_types:{Region:'text'}};
    builderState.rows = [{Region:'North'}];
    setCharts([{id:'chart',title:'Regions',type:'bar',x:'Region',aggregation:'count',layout:{x:0,y:0,w:6,h:7}}]);
    window.draw=renderVisuals;
  `);
  const tick = () => new Promise(resolve => setTimeout(resolve, 50));
  w.draw(); w.draw(); w.draw();
  await tick(); assert.equal(calls, 1, 'same-frame requests coalesce');
  w.draw(); await tick(); assert.equal(purges, 0);
  pending.shift()(); await tick(); assert.equal(calls, 2); assert.equal(purges, 1);
  pending.shift()(); await tick();
  dom.window.close();
  console.log('PASS: mounted rendering, coalesced updates, no purge during async Plotly render');
})().catch(error => {console.error(error);process.exit(1);});
