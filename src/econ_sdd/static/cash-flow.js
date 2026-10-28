'use strict';
// Monthly input collection and presentation. Python owns all financial arithmetic.
const $ = id => document.getElementById(id);
const csrf=document.querySelector('meta[name="csrf-token"]').content;
const state={config:null,income:[],expenses:[],source:'manual',sampleDerived:false,name:'',record:null,stale:false,busy:false,revision:0,nextId:0};
const fieldControls=new Map();
const make=(tag,className,text)=>{const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el;};
const currencyInfo=()=>state.config?.currencies.find(c=>c.code===$('currency').value)||{code:'USD',symbol:'$',minor_digits:2};
function newItem(label='',amount=''){return {id:++state.nextId,label,amount};}
function sourceTag(){return state.source==='sample'?'Sample':state.sampleDerived?'Sample-derived':'Manual';}
function downloads(){const disabled=!state.record||state.stale||state.busy;$('save-json').disabled=disabled;$('save-csv').disabled=disabled;document.dispatchEvent(new Event('econ:calculator-state'));}
function busy(value){state.busy=value;$('calculate-cash').disabled=value||!state.config;$('calculate-cash').textContent=value?'Calculating…':'Calculate cash flow ↗';$('open-budget').disabled=value||!state.config;$('cash-result').setAttribute('aria-busy',String(value));downloads();}
function clearErrors(){for(const {input,error} of fieldControls.values()){input.removeAttribute('aria-invalid');error.hidden=true;}$('income-error').hidden=true;$('expenses-error').hidden=true;$('form-error').hidden=true;}
function showErrors(errors){clearErrors();let first=null;const general=[];for(const [key,message] of Object.entries(errors)){const control=fieldControls.get(key);if(control){control.input.setAttribute('aria-invalid','true');control.error.textContent=message;control.error.hidden=false;first ||= control.input;}else if(key==='income'||key==='expenses'){$(key+'-error').textContent=message;$(key+'-error').hidden=false;}else general.push(message);}if(general.length){$('form-error').textContent=general.join(' ');$('form-error').hidden=false;}first?.focus();}
function changed(){state.revision++;state.source='manual';$('source-tag').textContent=sourceTag();clearErrors();if(state.record){state.stale=true;$('cash-result').classList.add('ec-stale');$('stale-message').hidden=false;$('result-badge').textContent='Out of date';}downloads();}
function renderRows(){
  fieldControls.clear();const currency=currencyInfo();
  for(const group of ['income','expenses']){
    const root=$(group+'-rows');root.replaceChildren();
    state[group].forEach((item,index)=>{
      const row=make('div','ec-cash-row');const singular=group==='income'?'Income':'Expense';
      for(const field of ['label','amount']){
        const label=make('label','ec-field');const id='cash-'+item.id+'-'+field;label.htmlFor=id;
        label.append(make('span','ec-label',field==='label'?'Category':'Monthly amount'));
        const wrap=make('span','ec-input-wrap');const input=make('input');input.id=id;input.type=field==='label'?'text':'number';input.value=item[field];
        input.setAttribute('aria-label',singular+' '+(field==='label'?'category':'amount')+' '+(index+1)+(field==='amount'?' ('+currency.code+' per month)':''));
        if(field==='label'){input.maxLength=80;input.placeholder=group==='income'?'e.g. Take-home pay':'e.g. Housing';}
        else {input.min='0';input.max='1000000000000';input.step=String(10**-currency.minor_digits);input.inputMode='decimal';input.placeholder=currency.minor_digits?'0.'+'0'.repeat(currency.minor_digits):'0';wrap.append(make('span','ec-money-symbol',currency.symbol));}
        const error=make('span','ec-field-error');error.id=id+'-error';error.hidden=true;input.setAttribute('aria-describedby',error.id);
        input.addEventListener('input',()=>{item[field]=input.value;changed();});
        wrap.append(input);label.append(wrap,error);row.append(label);fieldControls.set(group+'.'+index+'.'+field,{input,error});
      }
      const remove=make('button','ec-cash-remove','×');remove.type='button';remove.disabled=state[group].length===1;remove.title='Remove category';remove.setAttribute('aria-label','Remove '+singular.toLowerCase()+' category '+(index+1));
      remove.addEventListener('click',()=>{state[group].splice(index,1);changed();renderRows();$(group==='income'?'add-income':'add-expense').focus();});
      row.append(remove);root.append(row);
    });
    $(group==='income'?'add-income':'add-expense').disabled=state[group].length>=50;
  }
  document.querySelectorAll('[data-money-code]').forEach(el=>el.textContent=currency.code);
}
function budget(){return {schema_version:1,calculation_mode:'cash_flow',currency:$('currency').value,source:state.source,sample_derived:state.sampleDerived,name:state.name,
  ...Object.fromEntries(['income','expenses'].map(group=>[group,state[group].map(({label,amount})=>({label,amount}))]))};}
async function post(path,data,raw=false){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},credentials:'same-origin',cache:'no-store',body:raw?data:JSON.stringify(data)});if(!response.ok){const body=await response.json().catch(()=>({errors:{form:'The local calculator could not complete this request.'}}));const error=new Error('Request could not be completed.');error.fields=body.errors;throw error;}return response;}
function applyRecord(record){
  state.record=record;state.stale=false;$('empty-result').hidden=true;$('result-content').hidden=false;$('stale-message').hidden=true;$('cash-result').classList.remove('ec-stale');$('result-badge').textContent='Monthly budget';
  const currency=record.budget.currency;const status=record.summary.status;
  $('cash-result').classList.toggle('ec-cash-shortfall',status==='shortfall');
  $('net-cash-flow').replaceChildren(document.createTextNode(record.display.summary.net_cash_flow+' '),make('span','',currency+' / month'));
  $('net-explanation').textContent=status==='surplus'?'Monthly surplus · left before savings allocations.':status==='shortfall'?'Monthly shortfall · expenses exceed income by this amount.':'Balanced · all entered income is allocated to expenses.';
  $('total-income').textContent=record.display.summary.total_income;$('total-expenses').textContent=record.display.summary.total_expenses;$('spending-share').textContent=record.display.spending_share_percent;
  const breakdown=$('expense-breakdown');breakdown.replaceChildren();
  record.display.expenses.forEach((item,index)=>{const category=make('div','ec-cash-category');const heading=make('div','ec-cash-category-heading');heading.append(make('span','',item.label),make('strong','',item.amount));const track=make('div','ec-cash-track');const bar=make('div','ec-cash-fill');const share=record.expense_breakdown[index].share_percent;bar.style.width=String(share===null?0:Math.min(100,Math.max(0,Number(share)) ))+'%';track.append(bar);track.setAttribute('role','img');track.setAttribute('aria-label',item.label+': '+item.amount+' '+currency+', '+item.share_percent+' of expenses');category.append(heading,track,make('p','ec-cash-share',share===null?'No expenses to compare':item.share_percent+' of expenses'));breakdown.append(category);});
  $('result-source').textContent=record.budget.source==='sample'?'Synthetic example':record.budget.sample_derived?'Manual · derived from sample':'Manual inputs';$('result-model').textContent=record.model_version;$('result-time').textContent=new Date(record.calculated_at_utc).toLocaleString();downloads();
  if(window.matchMedia('(max-width:680px)').matches)$('cash-result').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth',block:'start'});
}
async function calculate(){if(!state.config||state.busy)return;clearErrors();const revision=state.revision;busy(true);try{const response=await post('/api/cash-flow',budget());const record=await response.json();if(revision===state.revision)applyRecord(record);}catch(error){if(revision===state.revision)showErrors(error.fields||{form:'Cannot reach the local Python calculator. Check that it is running, then try again.'});}finally{busy(false);}}
function setInputs(value){state.income=value.income.map(item=>newItem(item.label,item.amount));state.expenses=value.expenses.map(item=>newItem(item.label,item.amount));state.source=value.source||'manual';state.sampleDerived=Boolean(value.sample_derived);state.name=value.name||'';$('currency').value=value.currency;renderRows();$('source-tag').textContent=sourceTag();clearErrors();}
function clear(){state.revision++;state.record=null;state.stale=false;setInputs({income:[{label:'Take-home pay',amount:''}],expenses:[{label:'Housing',amount:''}],currency:$('currency').value});$('empty-result').hidden=false;$('result-content').hidden=true;$('cash-result').classList.remove('ec-stale','ec-cash-shortfall');downloads();}
async function download(kind){if(!state.record||state.stale||state.busy)return;const revision=state.revision;busy(true);try{const response=await post('/api/cash-flow/export/'+kind,state.record.budget);const blob=await response.blob();if(revision!==state.revision)return;const url=URL.createObjectURL(blob),link=make('a');link.href=url;link.download='econ-cash-flow-'+state.record.budget.currency+'.'+kind;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){if(revision===state.revision)showErrors(error.fields||{form:'The download could not be prepared. Try again.'});}finally{busy(false);}}
async function importFile(file){if(!file||state.busy||!state.config)return;if(file.size>state.config.max_upload_bytes){showErrors({file:'Choose a JSON file no larger than 1 MiB.'});$('budget-file').value='';return;}const revision=state.revision;clearErrors();busy(true);try{const text=await file.text();const response=await post('/api/cash-flow/import',text,true);const record=await response.json();if(revision!==state.revision)return;state.revision++;setInputs(record.budget);applyRecord(record);}catch(error){if(revision===state.revision)showErrors(error.fields||{file:'Cannot open this budget. Choose a valid cash flow JSON file.'});}finally{$('budget-file').value='';busy(false);}}
$('cash-form').addEventListener('submit',event=>{event.preventDefault();calculate();});
for(const [id,group] of [['add-income','income'],['add-expense','expenses']])$(id).addEventListener('click',()=>{if(state[group].length>=50)return;state[group].push(newItem());changed();renderRows();fieldControls.get(group+'.'+(state[group].length-1)+'.label').input.focus();});
$('currency').addEventListener('change',()=>{changed();renderRows();});
$('load-example').addEventListener('click',()=>{if(!state.config||state.busy)return;state.revision++;setInputs({currency:$('currency').value,source:'sample',sample_derived:true,income:[{label:'Take-home pay',amount:'4200'},{label:'Other income',amount:'300'}],expenses:[{label:'Housing',amount:'1600'},{label:'Utilities',amount:'200'},{label:'Food',amount:'450'},{label:'Transport',amount:'250'},{label:'Other spending',amount:'500'}]});if(state.record){state.stale=true;$('cash-result').classList.add('ec-stale');$('stale-message').hidden=false;$('result-badge').textContent='Out of date';}downloads();calculate();});
$('clear').addEventListener('click',clear);$('save-json').addEventListener('click',()=>download('json'));$('save-csv').addEventListener('click',()=>download('csv'));$('open-budget').addEventListener('click',()=>$('budget-file').click());$('budget-file').addEventListener('change',()=>importFile($('budget-file').files[0]));
clear();busy(false);
fetch('/api/config',{cache:'no-store',credentials:'same-origin'}).then(response=>{if(!response.ok)throw new Error();return response.json();}).then(config=>{state.config=config;$('currency').replaceChildren();for(const currency of config.currencies){const option=make('option','',currency.code+' · '+currency.name);option.value=currency.code;$('currency').append(option);}$('currency').value=config.default_currency;$('app-version').textContent='Econ '+config.app_version+' · '+config.cash_flow_model_version;renderRows();busy(false);}).catch(()=>{showErrors({form:'Cannot load the local calculator. Refresh the page after starting Python.'});$('calculate-cash').textContent='Calculator unavailable';});
window.econCalculator={
  ready:()=>Boolean(state.config),revision:()=>state.revision,
  capture:()=>!state.record||state.stale||state.busy?null:{kind:'cash_flow',inputs:state.record.budget},
  accepts:kind=>kind==='cash_flow',
  load:record=>{state.revision++;setInputs(record.budget);applyRecord(record);},
  reset:()=>{clear();busy(false);}
};
