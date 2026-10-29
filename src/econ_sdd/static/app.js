'use strict';

// Inputs and rendering only. All authoritative financial results come from Python.
const $ = id => document.getElementById(id);
const state = {mode:'projection',config:null,record:null,revision:0,busy:false,stale:false,timing:'end',
  source:'manual',sampleDerived:false,name:'',page:0,requestId:0};
const moneyFields = ['initial_balance','monthly_contribution','goal_amount'];
const projectionFields = ['initial_balance','monthly_contribution','annual_effective_rate_percent','duration_months'];
const fields = [...moneyFields,'annual_effective_rate_percent','duration_months','start_date','target_date'];
const csrf = document.querySelector('meta[name="csrf-token"]').content;

function todayLocalISO() {
  const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
}
function dateLabel(iso) {
  return new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(iso+'T00:00:00Z'));
}
function exampleTarget(start) {
  const [y,m,d]=start.split('-').map(Number),year=y+2;
  const lastDay=new Date(year,m,0).getDate();
  return [year,String(m).padStart(2,'0'),String(Math.min(d,lastDay)).padStart(2,'0')].join('-');
}
function actionLabel() {
  $('calculate').textContent=state.busy?'Calculating…':state.mode==='goal'?'Calculate monthly saving ↗':'Calculate savings ↗';
}
function setMode(mode,{invalidate=true}={}) {
  if(state.busy&&invalidate)return;
  const changed=state.mode!==mode;
  state.mode=mode;
  $('savings-form').classList.toggle('ec-goal-input-mode',mode==='goal');
  document.querySelectorAll('[data-mode]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.mode===mode)));
  $('goal-amount-field').hidden=mode!=='goal';$('goal-dates').hidden=mode!=='goal';
  $('deposit-field').hidden=mode==='goal';$('duration-field').hidden=mode==='goal';
  $('empty-heading').textContent=mode==='goal'?'Make a plan for your goal.':'Your projection starts here.';
  $('empty-description').textContent=mode==='goal'?'Enter a target amount and date to calculate the monthly deposit needed under your assumptions.':'Enter your savings assumptions, or load the illustrative example to explore the calculator.';
  actionLabel();clearErrors();
  if(invalidate&&changed){state.revision++;state.record=null;state.stale=false;$('empty-result').hidden=false;$('result-content').hidden=true;$('result').classList.remove('ec-stale');updateDownloads();}
}

function horizon(months) {
  if (months === 0) return '0 months';
  if (months % 12 === 0) return (months/12)+' '+(months===12?'year':'years');
  const years=Math.floor(months/12),rest=months%12;
  return years ? years+'y '+rest+'m' : months+' '+(months===1?'month':'months');
}
function currencyInfo() {
  return state.config?.currencies.find(c=>c.code===$('currency').value) || {code:'USD',symbol:'$',minor_digits:2};
}
function sourceTag() {
  $('source-tag').textContent = state.source==='sample'?'Sample':state.sampleDerived?'Sample-derived':'Manual';
}
function updateCurrencyLabels() {
  const c=currencyInfo();
  document.querySelectorAll('[data-money-code]').forEach(el=>el.textContent=c.code);
  document.querySelectorAll('[data-money-symbol]').forEach(el=>el.textContent=c.symbol);
  moneyFields.forEach(id=>{$(id).step=String(10**-c.minor_digits);$(id).placeholder=c.minor_digits?'0.'+'0'.repeat(c.minor_digits):'0';});
}
function updateDuration() {
  const raw=$('duration_months').value,n=Number(raw);
  $('duration-caption').textContent=raw!==''&&Number.isInteger(n)&&n>=0&&n<=1200?horizon(n):'0–1,200 months';
  if(Number.isFinite(n)&&n>=0&&n<=1200)$('duration-slider').value=String(n);
}
function setTiming(timing) {
  state.timing=timing;
  document.querySelectorAll('[data-timing]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.timing===timing)));
}
function clearErrors() {
  fields.forEach(id=>{$(id).removeAttribute('aria-invalid');$(id+'-error').hidden=true;});
  $('form-error').hidden=true;
}
function showErrors(errors) {
  clearErrors();let first=null;const general=[];
  for(const [key,message] of Object.entries(errors)) {
    if(fields.includes(key)) {
      $(key).setAttribute('aria-invalid','true');$(key+'-error').textContent=message;$(key+'-error').hidden=false;
      first ||= $(key);
    } else general.push(message);
  }
  if(general.length){$('form-error').textContent=general.join(' ');$('form-error').hidden=false;}
  first?.focus();
}
function setBusy(busy) {
  state.busy=busy;$('calculate').disabled=busy||!state.config;
  actionLabel();
  $('result').setAttribute('aria-busy',String(busy));
  updateDownloads();
}
function updateDownloads() {
  const disabled=!state.record||state.stale||state.busy;
  $('save-json').disabled=disabled;$('save-csv').disabled=disabled;document.dispatchEvent(new Event('econ:calculator-state'));
}
function markStale({edited=true}={}) {
  state.revision++;
  if(edited)state.source='manual';
  sourceTag();
  if(state.record){state.stale=true;$('result').classList.add('ec-stale');$('stale-message').hidden=false;
    $('result-badge').textContent='Out of date';}
  updateDownloads();
}
function scenario() {
  if(state.mode==='goal')return {schema_version:1,calculation_mode:'goal',initial_balance:$('initial_balance').value,goal_amount:$('goal_amount').value,annual_effective_rate_percent:$('annual_effective_rate_percent').value,start_date:$('start_date').value,target_date:$('target_date').value,contribution_timing:state.timing,currency:$('currency').value,source:state.source,sample_derived:state.sampleDerived,name:state.name};
  const duration=$('duration_months').value;
  return {schema_version:1,initial_balance:$('initial_balance').value,
    monthly_contribution:$('monthly_contribution').value,
    annual_effective_rate_percent:$('annual_effective_rate_percent').value,
    duration_months:duration===''?null:Number(duration),contribution_timing:state.timing,
    currency:$('currency').value,source:state.source,sample_derived:state.sampleDerived,name:state.name};
}
async function post(path,data,raw=false) {
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
    credentials:'same-origin',cache:'no-store',body:raw?data:JSON.stringify(data)});
  if(!response.ok) {
    const value=await response.json().catch(()=>({errors:{form:'The local calculator could not complete this request.'}}));
    const error=new Error('Request could not be completed.');error.fields=value.errors;throw error;
  }
  return response;
}
async function calculate() {
  if(!state.config||state.busy)return;
  clearErrors();const rev=state.revision,request=++state.requestId;setBusy(true);
  try {
    const response=await post(state.mode==='goal'?'/api/goal':'/api/calculate',scenario());const record=await response.json();
    if(rev===state.revision&&request===state.requestId)applyRecord(record);
  } catch(error) {
    if(rev===state.revision){showErrors(error.fields||{form:'Cannot reach the local Python calculator. Check that it is running, then try again.'});
      if(state.record)markStale({edited:false});}
  } finally {if(request===state.requestId)setBusy(false);}
}
function applyRecord(record) {
  state.record=record;state.stale=false;state.page=0;
  $('empty-result').hidden=true;$('result-content').hidden=false;
  $('result').classList.remove('ec-stale');$('stale-message').hidden=true;$('result-badge').textContent='Projection';
  const s=record.scenario,display=record.display;
  $('goal-summary').hidden=!record.goal;$('goal-legend').hidden=!record.goal;
  $('result').classList.toggle('ec-goal-result',Boolean(record.goal));
  $('result-horizon-label').textContent=record.goal?'Projected balance by':'Projected balance in';
  $('result-horizon').textContent=record.goal?dateLabel(record.goal_result.modeled_end_date):horizon(s.duration_months);
  $('schedule-time-heading').textContent=record.goal?'Period end':'Month';
  $('goal-schedule-note').textContent=record.goal?'Dates show period-end balances; the partial final month is excluded. ':'';
  if(record.goal) {
    const g=record.goal,r=record.goal_result,d=display.goal;
    $('goal-monthly').replaceChildren(document.createTextNode(d.required_monthly_contribution));
    const goalCode=document.createElement('span');goalCode.textContent=g.currency;$('goal-monthly').append(goalCode);
    $('goal-target-copy').textContent='To reach '+d.goal_amount+' by '+dateLabel(g.target_date)+'.';
    $('goal-period-copy').textContent=r.complete_months+' complete monthly '+(r.complete_months===1?'period':'periods')+' · modeled through '+dateLabel(r.modeled_end_date)+(r.unused_days?' · '+r.unused_days+' partial-month '+(r.unused_days===1?'day':'days')+' excluded.':'.');
    $('goal-rounding-copy').textContent=r.status==='no_additional_deposit'?'The projected starting balance covers this goal without additional monthly deposits.':'Rounded upward to the currency’s smallest unit and checked against the forward projection. This depends on the entered rate and making every deposit.';
    $('goal-first-date').textContent=r.first_deposit_date?dateLabel(r.first_deposit_date):'No new deposit required';
    $('goal-last-date').textContent=r.last_deposit_date?dateLabel(r.last_deposit_date):'No new deposit required';
    $('goal-surplus').textContent=d.surplus;
    $('monthly_contribution').value=s.monthly_contribution;$('duration_months').value=s.duration_months;updateDuration();
  }
  $('ending-balance').replaceChildren(document.createTextNode(display.summary.ending_balance));
  const code=document.createElement('span');code.textContent=s.currency;$('ending-balance').append(code);
  $('total-deposited').textContent=display.summary.total_deposited;
  $('total-interest').textContent=display.summary.interest;
  $('interest-label').textContent=display.interest_negative?'Interest lost':'Interest earned';
  $('result-note').textContent=display.interest_negative?'Negative-rate stress assumption. Future rates may differ.':'A possible outcome under these assumptions.';
  $('assumption-timing').textContent=s.contribution_timing==='end'?'Month-end deposits':'Month-start deposits';
  $('result-source').textContent=s.source==='sample'?'Illustrative sample inputs':s.sample_derived?'Manual inputs derived from a sample':'Manual inputs';
  $('result-model').textContent=record.model_version;
  $('result-time').textContent=record.calculated_at_utc.replace('T',' ')+' (UTC)';
  $('monthly-rate').textContent=display.monthly_rate_percent;
  $('growth-share').textContent=display.balance_zero?'No balance to compare':display.interest_negative?'Negative-rate scenario':display.growth_share_percent+'% of balance from interest';
  $('breakdown-bar').hidden=display.interest_negative||display.balance_zero;
  const share=Number(display.growth_share_percent);
  $('deposit-bar').style.width=(100-share)+'%';$('interest-bar').style.width=share+'%';
  $('breakdown-bar').setAttribute('aria-label',(100-share)+' percent deposits, '+share+' percent projected interest');
  const select=$('schedule-period');select.replaceChildren();
  const pages=Math.max(1,Math.ceil(s.duration_months/12));
  for(let page=0;page<pages;page++) {
    const option=document.createElement('option');option.value=String(page);
    option.textContent='Months '+(page===0?0:page*12+1)+'–'+Math.min(s.duration_months,(page+1)*12);select.append(option);
  }
  $('schedule-currency').textContent=s.currency;
  renderSchedule();renderChart();updateDownloads();
  if(window.matchMedia('(max-width:680px)').matches)$('result').scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});
}
function renderSchedule() {
  if(!state.record)return;
  const start=state.page===0?0:state.page*12+1,end=Math.min(state.record.rows.length,(state.page+1)*12+1);
  const body=$('schedule-body');body.replaceChildren();
  state.record.display.rows.slice(start,end).forEach(row=>{
    const tr=document.createElement('tr');
    [state.record.goal?dateLabel(state.record.rows[row.month_index].closing_date):row.month_index,row.total_deposited,row.cumulative_interest,row.closing_balance].forEach(value=>{
      const td=document.createElement('td');td.textContent=String(value);tr.append(td);
    });body.append(tr);
  });
}
function renderChart() {
  const box=$('growth-chart'),record=state.record;
  if(!record||$('chart-panel').hidden)return;
  const width=Math.floor(box.getBoundingClientRect().width);if(width<80)return;
  const rows=record.rows,n=record.scenario.duration_months,currency=record.scenario.currency;
  const height=265,left=currency==='KWD'?84:68,right=12,top=27,bottom=43,pw=width-left-right,ph=height-top-bottom;
  const maximum=Math.max(1,record.goal?Number(record.goal.goal_amount):0,...rows.map(row=>Math.max(Number(row.closing_balance),Number(row.total_deposited))));
  const base=10**Math.floor(Math.log10(maximum)),ceiling=Math.ceil(maximum/base*2)/2*base;
  const x=month=>n===0?left+pw/2:left+pw*month/n,y=value=>top+ph-Number(value)/ceiling*ph;
  const line=key=>rows.map((row,index)=>(index?'L':'M')+x(row.month_index).toFixed(2)+','+y(row[key]).toFixed(2)).join(' ');
  const balance=line('closing_balance'),deposits=line('total_deposited');let ticks='',grid='';
  const format=new Intl.NumberFormat('en-US',{style:'currency',currency,notation:maximum>1e15?'scientific':'compact',maximumFractionDigits:1});
  for(let i=0;i<=4;i++) {
    const value=ceiling*i/4,py=y(value);
    grid+='<line x1="'+left+'" x2="'+(width-right)+'" y1="'+py+'" y2="'+py+'" stroke="var(--ec-line)" stroke-width="1"/>'+
      '<text x="'+(left-9)+'" y="'+(py+4)+'" text-anchor="end">'+format.format(value)+'</text>';
  }
  const count=width<350?3:4;
  for(let i=0;i<=count;i++) {
    if(n===0&&i>0)break;
    const month=n*i/count,px=n===0?left+pw/2:left+pw*i/count;
    const label=n>=24?Number((month/12).toFixed(1)):Math.round(month);
    ticks+='<text x="'+px+'" y="'+(height-20)+'" text-anchor="'+(n===0?'middle':i===0?'start':i===count?'end':'middle')+'">'+label+'</text>';
  }
  const last=rows.at(-1),display=record.display.rows;
  box.innerHTML='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Conditional savings projection in '+currency+'">'+
    '<title>Projected balance and total deposited in '+currency+'</title><desc>Values come from the Python savings engine. Dashed line: deposits. Solid line: projected balance. Results depend on entered assumptions.</desc>'+
    '<defs><linearGradient id="savings-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="var(--ec-accent)" stop-opacity=".15"/><stop offset="100%" stop-color="var(--ec-accent)" stop-opacity="0"/></linearGradient></defs>'+
    '<text x="'+left+'" y="12">Balance · '+currency+'</text>'+grid+
    '<path d="'+balance+' L'+x(n)+','+y(0)+' L'+x(0)+','+y(0)+' Z" fill="url(#savings-fill)"/>'+
    (record.goal?'<line x1="'+left+'" x2="'+(width-right)+'" y1="'+y(record.goal.goal_amount)+'" y2="'+y(record.goal.goal_amount)+'" stroke="var(--ec-muted)" stroke-width="1" stroke-dasharray="2 5"/>':'')+
    '<path d="'+deposits+'" fill="none" stroke="var(--ec-deposit)" stroke-width="1.6" stroke-dasharray="4 4"/>'+
    '<path d="'+balance+'" fill="none" stroke="var(--ec-accent)" stroke-width="2.6" stroke-linejoin="round"/>'+
    '<circle cx="'+x(n)+'" cy="'+y(last.closing_balance)+'" r="4" fill="var(--ec-accent)"/>'+ticks+
    '<text x="'+(left+pw/2)+'" y="'+(height-2)+'" text-anchor="middle">'+(n>=24?'Years':'Months')+'</text>'+
    '<line data-guide y1="'+top+'" y2="'+(height-bottom)+'" x1="0" x2="0" stroke="var(--ec-muted)" opacity="0"/>'+
    '<circle data-marker cx="0" cy="0" r="4" fill="var(--ec-accent)" opacity="0"/>'+
    '<rect data-hit x="'+left+'" y="'+top+'" width="'+pw+'" height="'+ph+'" fill="transparent"/></svg>';
  function readout(index) {
    $('chart-period').textContent=record.goal?dateLabel(rows[index].closing_date):'Month '+index;
    $('chart-value').textContent=display[index].closing_balance+' '+currency;
  }
  function reset(){readout(n);box.querySelector('[data-guide]').setAttribute('opacity','0');box.querySelector('[data-marker]').setAttribute('opacity','0');}
  function inspect(event){
    const rect=box.getBoundingClientRect(),position=Math.max(left,Math.min(width-right,event.clientX-rect.left));
    const month=n===0?0:Math.round((position-left)/pw*n),row=rows[month];readout(month);
    const guide=box.querySelector('[data-guide]'),marker=box.querySelector('[data-marker]');
    guide.setAttribute('x1',x(month));guide.setAttribute('x2',x(month));guide.setAttribute('opacity','.6');
    marker.setAttribute('cx',x(month));marker.setAttribute('cy',y(row.closing_balance));marker.setAttribute('opacity','1');
  }
  box.querySelector('[data-hit]').addEventListener('pointermove',inspect);
  box.querySelector('[data-hit]').addEventListener('pointerdown',inspect);
  box.querySelector('[data-hit]').addEventListener('pointerleave',reset);reset();
}
function setView(view) {
  const chart=view==='chart';$('chart-panel').hidden=!chart;$('schedule-panel').hidden=chart;
  $('chart-tab').setAttribute('aria-selected',String(chart));$('schedule-tab').setAttribute('aria-selected',String(!chart));
  if(chart)renderChart();
}
function setInputs(s,goal=null) {
  setMode(goal?'goal':'projection',{invalidate:false});
  projectionFields.forEach(id=>$(id).value=String(s[id]??''));
  if(goal)['goal_amount','start_date','target_date'].forEach(id=>$(id).value=String(goal[id]));$('currency').value=s.currency;setTiming(s.contribution_timing);
  state.source=s.source;state.sampleDerived=s.sample_derived;state.name=s.name||'';
  updateCurrencyLabels();updateDuration();sourceTag();
}
async function download(kind) {
  if(!state.record||state.stale||state.busy)return;
  clearErrors();const savedScenario=state.record.goal||state.record.scenario;setBusy(true);
  try {
    const response=await post('/api/export/'+kind,savedScenario);
    const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=(savedScenario.calculation_mode==='goal'?'econ-goal-':'econ-savings-')+savedScenario.currency+'.'+kind;document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch(error){showErrors(error.fields||{form:'The download could not be prepared. Try again.'});}
  finally {setBusy(false);}
}
async function importFile(file) {
  if(!file||state.busy||!state.config)return;
  if(file.size>state.config.max_upload_bytes){showErrors({file:'Choose a JSON file no larger than 1 MiB.'});return;}
  clearErrors();markStale({edited:false});const rev=state.revision,request=++state.requestId;setBusy(true);
  try {
    const response=await post('/api/import',await file.text(),true),record=await response.json();
    if(rev===state.revision&&request===state.requestId){setInputs(record.scenario,record.goal||null);applyRecord(record);}
  } catch(error){showErrors(error.fields||{file:'The JSON file could not be loaded. Check its format and try again.'});}
  finally {if(request===state.requestId)setBusy(false);$('scenario-file').value='';}
}
fields.forEach(id=>$(id).addEventListener('input',()=>{if(id==='duration_months')updateDuration();markStale();}));
$('duration-slider').addEventListener('input',()=>{$('duration_months').value=$('duration-slider').value;updateDuration();markStale();});
$('currency').addEventListener('change',()=>{updateCurrencyLabels();markStale({edited:false});});
document.querySelectorAll('[data-timing]').forEach(button=>button.addEventListener('click',()=>{setTiming(button.dataset.timing);markStale();}));
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.mode)));
$('start_date').value=todayLocalISO();
$('calculate').addEventListener('click',calculate);
$('savings-form').addEventListener('submit',event=>{event.preventDefault();calculate();});
$('savings-form').addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.tagName==='INPUT'){event.preventDefault();calculate();}});
$('load-example').addEventListener('click',()=>{
  if(state.busy)return;
  const isGoal=state.mode==='goal',currency=$('currency').value;
  markStale({edited:false});
  if(isGoal) {
    const start=todayLocalISO();
    const g={initial_balance:'1000',goal_amount:'5000',annual_effective_rate_percent:'5',start_date:start,target_date:exampleTarget(start),contribution_timing:'end',currency,source:'sample',sample_derived:true,name:''};
    setInputs({...g,monthly_contribution:'0',duration_months:24},g);
  } else setInputs({initial_balance:'10000',monthly_contribution:'250',annual_effective_rate_percent:'5',duration_months:120,contribution_timing:'end',currency,source:'sample',sample_derived:true,name:''});
  calculate();
});
$('clear').addEventListener('click',()=>{
  state.revision++;state.record=null;state.stale=false;state.source='manual';state.sampleDerived=false;state.name='';clearErrors();
  moneyFields.concat(['annual_effective_rate_percent']).forEach(id=>$(id).value='');$('duration_months').value='120';$('start_date').value=todayLocalISO();$('target_date').value='';setTiming('end');
  updateDuration();sourceTag();$('empty-result').hidden=false;$('result-content').hidden=true;$('result').classList.remove('ec-stale');updateDownloads();
});
$('chart-tab').addEventListener('click',()=>setView('chart'));$('schedule-tab').addEventListener('click',()=>setView('schedule'));
$('schedule-period').addEventListener('change',()=>{state.page=Number($('schedule-period').value);renderSchedule();});
$('save-json').addEventListener('click',()=>download('json'));$('save-csv').addEventListener('click',()=>download('csv'));
$('open-scenario').addEventListener('click',()=>$('scenario-file').click());
$('scenario-file').addEventListener('change',()=>importFile($('scenario-file').files[0]));
new ResizeObserver(renderChart).observe($('growth-chart'));
document.fonts.ready.then(renderChart);
fetch('/api/config',{cache:'no-store',credentials:'same-origin'}).then(response=>{if(!response.ok)throw new Error();return response.json();}).then(config=>{
  state.config=config;$('currency').replaceChildren();
  config.currencies.forEach(c=>{const option=document.createElement('option');option.value=c.code;option.textContent=c.code+' · '+c.name;$('currency').append(option);});
  $('currency').value=config.default_currency;$('app-version').textContent='Finance '+config.app_version+' · '+config.model_version;
  updateCurrencyLabels();updateDuration();setBusy(false);
}).catch(()=>{showErrors({form:'Cannot load the local calculator. Refresh the page after starting Python.'});$('calculate').textContent='Calculator unavailable';});
window.econCalculator={
  ready:()=>Boolean(state.config),revision:()=>state.revision,
  capture:()=>!state.record||state.stale||state.busy?null:{kind:state.record.goal?'goal':'savings',inputs:state.record.goal||state.record.scenario},
  accepts:kind=>kind==='savings'||kind==='goal',
  load:record=>{state.revision++;state.requestId++;setBusy(false);setInputs(record.scenario,record.goal||null);clearErrors();applyRecord(record);},
  reset:()=>{state.requestId++;$('clear').click();setBusy(false);}
};
