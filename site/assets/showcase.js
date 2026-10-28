'use strict';
// Visual walkthroughs only; there are no user financial inputs or browser balances.
const tabs=[...document.querySelectorAll('[role="tab"]')];
function select(tab,focus=false){for(const item of tabs){const active=item===tab;item.setAttribute('aria-selected',String(active));item.tabIndex=active?0:-1;document.getElementById(item.getAttribute('aria-controls')).hidden=!active;}if(focus)tab.focus();}
for(const [index,tab] of tabs.entries()){
  tab.addEventListener('click',()=>select(tab));
  tab.addEventListener('keydown',event=>{let target;if(event.key==='ArrowRight')target=(index+1)%tabs.length;else if(event.key==='ArrowLeft')target=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')target=0;else if(event.key==='End')target=tabs.length-1;else return;event.preventDefault();select(tabs[target],true);});
}
