global.window={}; require(require('path').resolve(__dirname,'../../src/meridian/app/hier.js')); const H=window.MHier;
const yaml=JSON.parse(process.argv[2]);
const N=H.nodes(yaml.tree);
const base={us_large_cap:.30,us_small_mid_cap:.05,intl_developed_eq:.15,emerging_eq:.05,global_reits:.03,commodities:.02,us_core_bond:.20,us_long_treasury:.03,us_tips_short:.05,us_high_yield:.02,intl_bond_hedged:.05,em_debt:.02,cash:.03};
const r1=H.apply(N,base,{us_large_cap:2},'pp','parent');  // funded by SMID only
console.log(JSON.stringify([r1.w.us_large_cap.toFixed(4), r1.w.us_small_mid_cap.toFixed(4), r1.net.toFixed(6), r1.errors]));
const r2=H.apply(N,base,{equity:2, equity_intl:45},'pp','parent'); // mixed modes not possible; share separately
const r3=H.apply(N,base,{equity:57},'weight','parent'); const eq=H.W(r3.w,N.find(n=>n.id==='equity'));
console.log(JSON.stringify([eq.toFixed(4), r3.net.toFixed(6), (r3.w.us_large_cap/r3.w.intl_developed_eq).toFixed(4)]));
const r4=H.apply(N,base,{equity:57, equity_intl:45},'share','parent'); const intl=H.W(r4.w,N.find(n=>n.id==='equity_intl')), e4=H.W(r4.w,N.find(n=>n.id==='equity'));
console.log(JSON.stringify([e4.toFixed(4), (intl/e4).toFixed(4), r4.net.toFixed(6), r4.errors]));
const r5=H.apply(N,base,{us_large_cap:1, us_core_bond:-1},'pp','none'); console.log(JSON.stringify([r5.net.toFixed(6), r5.w.us_large_cap.toFixed(4), r5.w.us_small_mid_cap.toFixed(4)]));
const r6=H.apply(N,base,{cash:2},'pp','parent'); console.log(JSON.stringify([r6.net.toFixed(6), r6.w.cash.toFixed(4), r6.w.us_core_bond.toFixed(4)]));
const r7=H.apply(N,base,{emerging_eq:10},'rel','fund'); console.log(JSON.stringify([r7.net.toFixed(6), r7.w.emerging_eq.toFixed(4)]));
const S=H.nodes(yaml.tree,{us_large_cap:[{id:'A',name:'A'},{id:'B',name:'B'}]});
const r8=H.apply(S,{...base,us_large_cap:undefined,A:.20,B:.10},{A:1},'pp','parent'); console.log(JSON.stringify([r8.w.A.toFixed(4), r8.w.B.toFixed(4)]));
