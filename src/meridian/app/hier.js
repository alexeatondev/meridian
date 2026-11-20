/* Meridian asset hierarchy engine (levels 1-5), shared by the glide-path and tilt tables.
   MHier.nodes(tree, extra)  -> flat list in display order: {id, name, level, depth, parent, kids, leaves}
     extra (optional): {assetId: [{id, name}]} securities added under each asset class as level-5 leaves.
   MHier.apply(nodes, base, edits, mode, balance) -> {w, errors, net}
     base:  {leafId: weight (fraction)}; edits: {nodeId: number as typed}
     mode:  'pp' change in percentage points of the fund (absolute)
            'share' new share of the parent level, in %          (relative to the parent)
            'rel' change in % of the node's current weight        (relative to itself)
            'weight' new weight in % of the fund
     balance: 'parent' unedited siblings absorb the change pro rata (the parent's total is kept)
              'fund'   every leaf not under an edited node absorbs it pro rata
              'none'   nothing is balanced: the edits must net to zero (net is reported)
   Edits are applied level by level from the top, so a level-1 change (stocks vs bonds) and a level-2 change
   (US vs international within stocks) combine: the level-2 share applies to the new equity total. */
(function(){
  const EPS=1e-9;
  function nodes(tree, extra){
    const out=[];
    (function walk(list, depth, parent){
      for(const n of list){
        const leaf=!!n.asset, id=leaf?n.asset:n.id;
        const kids=leaf?((extra&&extra[n.asset])||[]):null;
        const node={id, name:n.name, level:n.level||depth+1, depth, parent, kids:[], leaves:[], asset:leaf?n.asset:null};
        out.push(node);
        if(parent) parent.kids.push(node);
        if(leaf){
          if(kids&&kids.length){ for(const s of kids){ const sn={id:s.id, name:s.name, level:5, depth:depth+1, parent:node, kids:[], leaves:[s.id], security:true, asset:n.asset}; out.push(sn); node.kids.push(sn); node.leaves.push(s.id); } }
          else node.leaves.push(id);
        } else walk(n.children||[], depth+1, node);
      }
    })(tree, 0, null);
    for(let i=out.length-1;i>=0;i--){ const n=out[i]; if(n.kids.length&&!n.security&&!n.asset) n.leaves=n.kids.flatMap(k=>k.leaves); }
    for(const n of out) n.leafSet=new Set(n.leaves);
    return out;
  }
  const W=(w,n)=>n.leaves.reduce((t,l)=>t+(w[l]||0),0);
  function apply(list, base, edits, mode, balance){
    const w={...base}, errors=[], lock={}, byDepth={};
    const edited=list.filter(n=>edits[n.id]!==undefined&&edits[n.id]!==''&&edits[n.id]!==null&&!isNaN(+edits[n.id]));
    for(const n of edited)(byDepth[n.depth]||(byDepth[n.depth]=[])).push(n);
    const depths=Object.keys(byDepth).map(Number).sort((a,b)=>a-b);
    const roots=list.filter(n=>!n.parent);
    for(const d of depths){
      // group edited nodes by parent so siblings balance together
      const groups=new Map();
      for(const n of byDepth[d]){ const k=n.parent?n.parent.id:'__root'; if(!groups.has(k)) groups.set(k,[]); groups.get(k).push(n); }
      for(const [pk, ed] of groups){
        const sibs=pk==='__root'?roots:ed[0].parent.kids, parentTot=pk==='__root'?1:W(w,ed[0].parent);
        let dsum=0; const targets=[];
        for(const n of ed){
          const cur=W(w,n), v=+edits[n.id];
          let t = mode==='pp'?cur+v/100 : mode==='share'?parentTot*v/100 : mode==='rel'?cur*(1+v/100) : v/100;
          if(t<-EPS){ errors.push(`${n.name}: would go below zero`); t=0; }
          targets.push([n,cur,Math.max(0,t)]); dsum+=Math.max(0,t)-cur;
        }
        for(const [n,cur,t] of targets){
          if(cur>EPS){ const f=t/cur; n.leaves.forEach(l=>{w[l]=(w[l]||0)*f}); }
          else if(t>EPS){ if(n.leaves.length===1) w[n.leaves[0]]=t; else { errors.push(`${n.name}: has no weight today to scale; change the level below it instead`); } }
          n.leaves.forEach(l=>{lock[l]=n});
        }
        if(Math.abs(dsum)<1e-12||balance==='none') continue;
        let pool;
        if(balance==='parent'){ pool=sibs.filter(s=>!ed.includes(s)).flatMap(s=>s.leaves); }
        else {   // the rest of the fund, or of the nearest edited level above (whose total is already set)
          const par=pk==='__root'?null:ed[0].parent, isAnc=o=>{for(let p=par;p;p=p.parent) if(p===o) return true; return false;};
          let anc=null; for(let p=par;p;p=p.parent) if(edited.includes(p)){anc=p;break;}
          const dom=anc?anc.leaves:Object.keys(w);
          pool=dom.filter(l=>!ed.some(n=>n.leafSet.has(l))&&(!lock[l]||isAnc(lock[l])));
        }
        const tot=pool.reduce((t,l)=>t+(w[l]||0),0);
        if(tot<=EPS){ errors.push(`${ed.map(n=>n.name).join(', ')}: nothing left to balance with${balance==='parent'?' at this level (use "pro rata across the fund" or edit a sibling)':''}`); continue; }
        if(tot-dsum<-EPS){ errors.push(`${ed.map(n=>n.name).join(', ')}: the rest of ${balance==='parent'?'this level':'the fund'} isn't big enough to fund this change`); continue; }
        const f=(tot-dsum)/tot; pool.forEach(l=>{w[l]=(w[l]||0)*f});
      }
    }
    const net=Object.values(w).reduce((t,x)=>t+x,0)-Object.values(base).reduce((t,x)=>t+x,0);
    return {w, errors, net};
  }
  // Views of a change under each cell: 'ba' today -> after (% of fund); 'pp' change in pp of the fund (the
  // children's changes add up to the parent's, and level 1 nets to zero); 'rel' change in the share of the
  // parent, in pp of the parent (siblings always net to zero, e.g. US +2 / international -2 inside equity).
  const VIEWS=[['ba','Today → after','The weight in % of the fund today and after the change'],
    ['pp','Change (pp of fund)','Each level\'s change in pp of the fund: the changes inside a level add up to the change of the level above, and level 1 nets to zero (e.g. Equity +1, Fixed income and Real assets −1 between them)'],
    ['rel','Change vs siblings (pp of parent)','The change in each asset class\'s share of the level above, so the changes inside every group net to zero (e.g. US +2, International −2 inside equity)']];
  function change(view, n, base, w, d){
    const c=W(base,n), a=w?W(w,n):c, dd=d==null?2:d;
    if(view==='rel'){ const pc=n.parent?W(base,n.parent):1, pa=n.parent?(w?W(w,n.parent):pc):1;
      return (pa>EPS?a/pa:0)-(pc>EPS?c/pc:0); }
    return a-c;
  }
  const fmt=(x,d)=>Math.abs(x)<5e-7?'0.00':(x>0?'+':'−')+Math.abs(x*100).toFixed(d==null?2:d);
  function sub(view, n, base, w, d){ // the small text under a cell
    const dd=d==null?1:d, c=W(base,n), a=w?W(w,n):null, ch=a!=null&&Math.abs(a-c)>1e-7;
    if(view==='ba'||!w) return ch?`${(c*100).toFixed(dd)}→<b>${(a*100).toFixed(dd)}</b>`:(c*100).toFixed(dd);
    const x=change(view,n,base,w);
    return Math.abs(x)<5e-7?'<span class="mh0">0.00</span>':`<b class="${x>0?'mhpos':'mhneg'}">${fmt(x)}</b>`;
  }
  // Net-change check: level 1 must net to zero, and inside each group the children's changes add up to the
  // group's change (pp view) or to zero (share-of-parent view). Returns {l1, worst, ok, groups:[{node, sum, parent}]}.
  function netCheck(list, base, w){
    const l1=list.filter(n=>!n.parent).reduce((t,n)=>t+W(w,n)-W(base,n),0), groups=[];
    let worst=Math.abs(l1);
    for(const n of list){ if(!n.kids.length||n.security) continue;
      const sum=n.kids.reduce((t,k)=>t+W(w,k)-W(base,k),0), par=W(w,n)-W(base,n);
      const rel=n.kids.reduce((t,k)=>t+change('rel',k,base,w),0);
      groups.push({node:n, sum, parent:par, rel}); worst=Math.max(worst, Math.abs(sum-par), Math.abs(rel)); }
    return {l1, worst, ok:worst<5e-6, groups};
  }
  window.MHier={nodes, apply, W, VIEWS, change, sub, netCheck, fmt};
})();
