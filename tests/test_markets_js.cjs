const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync('static/js/app.js','utf8');
const context={marketProvider:'Robinhood',state:{polls:[],markets:[{id:'r',provider:'Robinhood',underlying_exchange:'Rothera',question:'2026 House',probability:52,outcome:'Democratic',price_convention:'Bid/ask midpoint',spread_pp:2,flags:['Public quote']},{id:'k',provider:'Kalshi',question:'Kalshi only',probability:55,flags:[]}]},slicePage:rows=>rows.slice(0,2),esc:s=>String(s??'').replace(/</g,'&lt;'),pct:n=>n+'%',time:t=>t||'Unavailable',empty:(title)=>title};
vm.createContext(context);vm.runInContext(code.slice(code.indexOf('function marketPriceTime('),code.indexOf('function render(){')),context);
let html=vm.runInContext('renderComparisons()',context);assert.match(html,/Robinhood · Rothera/);assert.doesNotMatch(html,/Kalshi only/);assert.match(html,/aria-label="Market provider"/);
context.marketProvider='Kalshi';html=vm.runInContext('renderComparisons()',context);assert.match(html,/Kalshi only/);assert.doesNotMatch(html,/Robinhood · Rothera/);
context.marketProvider='all';html=vm.runInContext('renderComparisons()',context);assert.match(html,/Kalshi only/);assert.match(html,/Robinhood · Rothera/);
context.state.markets[0].underlying_exchange='<script>';assert.match(vm.runInContext('marketCard(state.markets[0])',context),/&lt;script>/);
console.log('Market provider filter, exchange attribution and escaping checks passed');

context.state.markets[0].price_convention='last trade';context.state.markets[0].last_trade_at='2026-10-01T12:00:00Z';context.state.markets[0].quote_updated_at='2026-11-02T12:00:00Z';const last=vm.runInContext('marketCard(state.markets[0])',context);assert.match(last,/Last trade: 2026-10-01/);assert.doesNotMatch(last,/Quote updated: 2026-11-02/);
