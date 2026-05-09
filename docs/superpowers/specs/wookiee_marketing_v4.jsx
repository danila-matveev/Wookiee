import React, { useState, useMemo } from 'react';
import {
  Search, Plus, X, Percent, Hash, Edit3, Check,
  RefreshCw, Package, LayoutDashboard, Megaphone,
  Users, Settings, BarChart3, Clock, ChevronRight,
  ChevronDown, CheckCircle, Calendar
} from 'lucide-react';

/* =========================================================
   WOOKIEE HUB · MARKETING v4
   v3.2 → v4:
   - Date range picker (два поля дат) вместо пресетов
   - Полная воронка: Частота → Перех → CR→корз → Корз → CR→зак → Заказы → CR перех→зак
   - Статус-редактор в стиле дизайн-системы
   - Деталка: воронка + конверсии полностью
   ⇄ SUPABASE
   ========================================================= */

const fmt = n => n == null ? '—' : n.toLocaleString('ru-RU');
const fmtR = n => n == null ? '—' : `${n.toLocaleString('ru-RU')} ₽`;
const pct = (a, b) => b > 0 ? `${((a / b) * 100).toFixed(1)}%` : '—';

// ======== WEEK DATES =======================================
// 40 недель: 28 июля 2025 → 27 апреля 2026

const WEEK_DATES = [];
{ let d = new Date(2025, 6, 28); // Jul 28 2025
  for (let i = 0; i < 40; i++) {
    const iso = d.toISOString().slice(0,10);
    const label = `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}`;
    WEEK_DATES.push({ iso, label });
    d = new Date(d.getTime() + 7*86400000);
  }
}
const FIRST_DATE = WEEK_DATES[0].iso;           // 2025-07-28
const LAST_DATE  = WEEK_DATES[39].iso;           // 2026-04-27
const DEFAULT_FROM = WEEK_DATES[36].iso;         // ~4 weeks ago: 2026-03-30
const DEFAULT_TO   = LAST_DATE;

// ======== PRODUCT MATRIX ⇄ SUPABASE =======================

const MODELS = [{ code:'Wendy' },{ code:'Audrey' },{ code:'Vuki' },{ code:'Moon' },{ code:'Ruby' },{ code:'Lia' },{ code:'Joy' },{ code:'Bella' },{ code:'Lana' },{ code:'Eva' },{ code:'Valery' }];
const COLORS_BY = { Wendy:['dark_beige','black','white','brown','nude'], Audrey:['nude','dusty_rose','sage','ivory','dark_beige','total_white'], Vuki:['чёрный','белый','бежевый'], Moon:['brown','white','pale_pink','lavender','washed_khaki'], Ruby:['white','pale_pink','brown','heart_pink'], Lia:['nude','black'], Joy:['black','brown'], Bella:['white','black','light_beige'], Lana:['white','dark_beige'], Eva:['black','white'], Valery:['white','black'] };
const SIZES = ['XS','S','M','L','XL'];
const SKUS = [
  { id:1, model:'Wendy', color:'dark_beige', size:'S', nm:'175569571' },
  { id:2, model:'Wendy', color:'white', size:'S', nm:'163151603' },
  { id:3, model:'Wendy', color:'brown', size:'S', nm:'257131227' },
  { id:4, model:'Wendy', color:'nude', size:'S', nm:'421569733' },
  { id:5, model:'Wendy', color:'black', size:'S', nm:'163151610' },
  { id:6, model:'Audrey', color:'nude', size:'S', nm:'96006524' },
  { id:7, model:'Audrey', color:'dark_beige', size:'S', nm:'246930819' },
  { id:8, model:'Audrey', color:'total_white', size:'S', nm:'421564101' },
  { id:9, model:'Vuki', color:'чёрный', size:'S', nm:'18336487' },
  { id:10,model:'Moon', color:'brown', size:'S', nm:'175567838' },
  { id:11,model:'Moon', color:'white', size:'S', nm:'165098576' },
  { id:12,model:'Ruby', color:'white', size:'S', nm:'98842349' },
  { id:13,model:'Ruby', color:'pale_pink', size:'S', nm:'216633352' },
  { id:14,model:'Joy', color:'black', size:'S', nm:'94723679' },
  { id:15,model:'Bella', color:'white', size:'S', nm:'257166805' },
  { id:16,model:'Bella', color:'light_beige', size:'S', nm:'257153640' },
  { id:17,model:'Bella', color:'black', size:'S', nm:'257144777' },
  { id:18,model:'set_vuki', color:'Magic_red', size:'S', nm:'362464637' },
  { id:19,model:'Lana', color:'dark_beige', size:'S', nm:'330530728' },
  { id:20,model:'Eva', color:'black', size:'S', nm:'460976740' },
  { id:21,model:'Valery', color:'white', size:'S', nm:'460976745' },
  { id:22,model:'Moon', color:'washed_khaki', size:'S', nm:'324724290' },
  { id:23,model:'VukiN', color:'чёрный', size:'S', nm:'161265945' },
  { id:24,model:'Charlotte', color:'brown', size:'S', nm:'681596813' },
];
const skuLabel = s => `${s.model}/${s.color}_${s.size}`;

// ======== GROUPS & ITEMS ===================================

const GROUPS = [
  { id:'brand',      label:'Брендированные запросы',  icon:'🔤' },
  { id:'external',   label:'Артикулы (внешний лид)',  icon:'📦' },
  { id:'cr_general', label:'Креаторы общие',          icon:'👥' },
  { id:'cr_personal',label:'Креаторы личные',         icon:'👤' },
];

const WS = { active:{label:'Используется',color:'green'}, free:{label:'Свободен',color:'blue'}, archive:{label:'Архив',color:'gray'} };

const ITEMS = [
  // БРЕНДИРОВАННЫЕ
  { id:'b1', group:'brand', query:'wooki',  art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:null },
  { id:'b2', group:'brand', query:'Вуки',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:null },
  { id:'b3', group:'brand', query:'wookei', art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:null },
  { id:'b4', group:'brand', query:'wokie',  art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:null },
  { id:'b5', group:'brand', query:'Vuki',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Vuki' },
  { id:'b6', group:'brand', query:'Moon',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Moon' },
  { id:'b7', group:'brand', query:'Ruby',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Ruby' },
  { id:'b8', group:'brand', query:'руби',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Ruby' },
  { id:'b9', group:'brand', query:'Audrey', art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Audrey' },
  { id:'b10',group:'brand', query:'одри',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Audrey' },
  { id:'b11',group:'brand', query:'Wendy',  art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Wendy' },
  { id:'b12',group:'brand', query:'венди',  art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Wendy' },
  { id:'b13',group:'brand', query:'Bella',  art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Bella' },
  { id:'b14',group:'brand', query:'Lana',   art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Lana' },
  { id:'b15',group:'brand', query:'Valery', art:null, nm:null, channel:'бренд', campaign:null, ww:null, status:'active', model:'Valery' },

  // АРТИКУЛЫ ВНЕШНИЙ ЛИД (query = номенклатура)
  { id:'e1', group:'external', query:'163151603', art:'Wendy/white',       nm:'163151603', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Wendy' },
  { id:'e2', group:'external', query:'421564101', art:'Audrey/total_white',nm:'421564101', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Audrey' },
  { id:'e3', group:'external', query:'460976740', art:'Eva/black',         nm:'460976740', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Eva' },
  { id:'e4', group:'external', query:'362464637', art:'set_vuki/Magic_red',nm:'362464637', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Vuki' },
  { id:'e5', group:'external', query:'421569733', art:'Wendy/nude',        nm:'421569733', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Wendy' },
  { id:'e6', group:'external', query:'257131227', art:'Wendy/brown',       nm:'257131227', channel:'Adblogger', campaign:null, ww:null, status:'active', model:'Wendy' },
  { id:'e7', group:'external', query:'246930819', art:'Audrey/dark_beige', nm:'246930819', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Audrey' },
  { id:'e8', group:'external', query:'98708431',  art:'Ruby/brown',        nm:'98708431',  channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Ruby' },
  { id:'e9', group:'external', query:'216633352', art:'Ruby/pale_pink',    nm:'216633352', channel:'Таргет ВК', campaign:null, ww:null, status:'active', model:'Ruby' },
  { id:'e10',group:'external', query:'94723679',  art:'Joy/black',         nm:'94723679',  channel:'Таргет ВК', campaign:null, ww:null, status:'active', model:'Joy' },
  { id:'e11',group:'external', query:'330530728', art:'Lana/dark_beige',   nm:'330530728', channel:'Adblogger', campaign:null, ww:null, status:'active', model:'Lana' },
  { id:'e12',group:'external', query:'257166805', art:'Bella/white',       nm:'257166805', channel:'Adblogger', campaign:null, ww:null, status:'active', model:'Bella' },
  { id:'e13',group:'external', query:'460976745', art:'Valery/white',      nm:'460976745', channel:'Яндекс',    campaign:null, ww:null, status:'active', model:'Valery' },

  // КРЕАТОРЫ ОБЩИЕ (query = WW-код)
  { id:'cg1', group:'cr_general', query:'WW121749', art:'компбел-ж-бесшов/чер_S', nm:'18336487',  channel:'креаторы', campaign:'VUKI_креаторы',  ww:'WW121749', status:'active', model:'Vuki' },
  { id:'cg2', group:'cr_general', query:'WW121769', art:'set_Wookiee/black_S',    nm:'161265945', channel:'креаторы', campaign:'SET_VUKI_креа',  ww:'WW121769', status:'active', model:'Vuki' },
  { id:'cg3', group:'cr_general', query:'WW121762', art:'Moon/brown_S',           nm:'175567838', channel:'креаторы', campaign:'MOON_креаторы',  ww:'WW121762', status:'active', model:'Moon' },
  { id:'cg4', group:'cr_general', query:'WW169464', art:'Moon/white_S',           nm:'165098576', channel:'креаторы', campaign:'Moon/white_кре', ww:'WW169464', status:'active', model:'Moon' },
  { id:'cg5', group:'cr_general', query:'WW121764', art:'Moon/washed_khaki_S',    nm:'324724290', channel:'креаторы', campaign:'MOON/W_креатор', ww:'WW121764', status:'active', model:'Moon' },
  { id:'cg6', group:'cr_general', query:'WW121790', art:'Wendy/dark_beige_S',     nm:'175569571', channel:'креаторы', campaign:'WENDY_креаторы', ww:'WW121790', status:'active', model:'Wendy' },
  { id:'cg7', group:'cr_general', query:'WW111103', art:'Wendy/brown_S',          nm:'257131227', channel:'креаторы', campaign:'Wendy/brown_кр', ww:'WW111103', status:'active', model:'Wendy' },
  { id:'cg8', group:'cr_general', query:'WW121752', art:'Audrey/nude_S',          nm:'96006524',  channel:'креаторы', campaign:'AUDREY_креатор', ww:'WW121752', status:'active', model:'Audrey' },
  { id:'cg9', group:'cr_general', query:'WW121755', art:'Ruby/white_S',           nm:'98842349',  channel:'креаторы', campaign:'RUBY_креаторы',  ww:'WW121755', status:'active', model:'Ruby' },
  { id:'cg10',group:'cr_general', query:'WW120794', art:'set_vuki/Magic_red_S',   nm:'362464637', channel:'креаторы', campaign:'Set_vuki/Magic', ww:'WW120794', status:'active', model:'Vuki' },
  { id:'cg11',group:'cr_general', query:'WW121774', art:'Joy/black_S',            nm:'94723679',  channel:'креаторы', campaign:'JOY_креаторы',   ww:'WW121774', status:'active', model:'Joy' },
  { id:'cg12',group:'cr_general', query:'WW121751', art:'Bella/light_beige_S',    nm:'257153640', channel:'креаторы', campaign:'BELLA_креатор',  ww:'WW121751', status:'active', model:'Bella' },
  { id:'cg13',group:'cr_general', query:'WW126256', art:'VukiN/чёрный_S',         nm:'161265945', channel:'креаторы', campaign:'VukiN_креаторы', ww:'WW126256', status:'active', model:'Vuki' },
  { id:'cg14',group:'cr_general', query:'WW180078', art:'Ruby/brown_S',           nm:'98708431',  channel:'креаторы', campaign:'Яндекс промост', ww:'WW180078', status:'active', model:'Ruby' },

  // КРЕАТОРЫ ЛИЧНЫЕ (query = WW-код)
  { id:'cp1', group:'cr_personal', query:'WW113490', art:'Wendy/white_S',        nm:'163151603', channel:'креаторы', campaign:'креатор_Шматов',  ww:'WW113490', status:'active', model:'Wendy' },
  { id:'cp2', group:'cr_personal', query:'WW114102', art:'Wendy/white_S',        nm:'163151603', channel:'креаторы', campaign:'креатор_Ворон',   ww:'WW114102', status:'active', model:'Wendy' },
  { id:'cp3', group:'cr_personal', query:'WW118332', art:'Wendy/white_S',        nm:'163151603', channel:'креаторы', campaign:'креатор_Донцов',  ww:'WW118332', status:'active', model:'Wendy' },
  { id:'cp4', group:'cr_personal', query:'WW113370', art:'Wendy/brown_S',        nm:'257131227', channel:'креаторы', campaign:'креатор_Первозв', ww:'WW113370', status:'active', model:'Wendy' },
  { id:'cp5', group:'cr_personal', query:'WW119646', art:'Wendy/brown_S',        nm:'257131227', channel:'креаторы', campaign:'креатор_Горшен',  ww:'WW119646', status:'active', model:'Wendy' },
  { id:'cp6', group:'cr_personal', query:'WW119649', art:'Wendy/brown_S',        nm:'257131227', channel:'креаторы', campaign:'креатор_Бажен',   ww:'WW119649', status:'active', model:'Wendy' },
  { id:'cp7', group:'cr_personal', query:'WW144016', art:'Audrey/nude_S',        nm:'96006524',  channel:'креаторы', campaign:'креатор_Шматов',  ww:'WW144016', status:'active', model:'Audrey' },
  { id:'cp8', group:'cr_personal', query:'WW123602', art:'set_vuki/Magic_red_S', nm:'362464637', channel:'креаторы', campaign:'креатор_Бородин', ww:'WW123602', status:'active', model:'Vuki' },
  { id:'cp9', group:'cr_personal', query:'WW110872', art:'Bella/light_beige_S',  nm:'257153640', channel:'креаторы', campaign:'креатор_Шматов',  ww:'WW110872', status:'active', model:'Bella' },
  { id:'cp10',group:'cr_personal', query:'WW251256', art:'Bella/light_beige_S',  nm:'257153640', channel:'креаторы', campaign:'креатор_Первозв', ww:'WW251256', status:'active', model:'Bella' },
  { id:'cp11',group:'cr_personal', query:'WW117140', art:'Ruby/white_S',         nm:'98842349',  channel:'креаторы', campaign:'креатор_Юдина',   ww:'WW117140', status:'active', model:'Ruby' },
  { id:'cp12',group:'cr_personal', query:'WW258410', art:'Valery/white',         nm:'460976745', channel:'креаторы', campaign:'креатор_Донцов',  ww:'WW258410', status:'active', model:'Valery' },
];

// ⇄ SUPABASE: marketing.search_query_stats_weekly
const genW = (peak, wks) => {
  const startIdx = 40 - wks;
  return Array.from({length: wks}, (_, i) => {
    const x = i/(wks-1||1), curve = Math.exp(-8*Math.pow(x-0.38,2));
    const f = Math.max(0, Math.round(peak*(0.02+0.98*curve)));
    const t = Math.round(f*(0.03+Math.random()*0.02));
    const a = Math.round(t*(0.15+Math.random()*0.1));
    const o = Math.round(a*(0.1+Math.random()*0.08));
    const wd = WEEK_DATES[startIdx + i] || WEEK_DATES[39];
    return { iso: wd.iso, week: wd.label, f, t, a, o };
  });
};

const WK = {};
ITEMS.forEach(item => {
  const peaks = { b1:259460,b2:1256,b3:0,b4:107,b5:291,b6:1,b7:126,b8:4,b9:1,b10:1,b11:24,b12:0,b13:4,b14:0,b15:0,
    e1:81,e2:1,e3:0,e4:361,e5:944,e6:784,e7:84,e8:350,e9:624,e10:54,e11:330,e12:12,e13:242,
    cg1:2090,cg2:0,cg3:120,cg4:0,cg5:60,cg6:4052,cg7:476,cg8:2240,cg9:460,cg10:408,cg11:9,cg12:6,cg13:216,cg14:0,
    cp1:368,cp2:0,cp3:6553,cp4:392,cp5:630,cp6:78,cp7:861,cp8:0,cp9:6,cp10:18,cp11:19,cp12:0 };
  const wks = item.group==='brand'?40:(item.group==='external'?30:20);
  WK[item.id] = genW(peaks[item.id]||10, wks);
});

// Aggregate weekly data within a date range
const aggRange = (id, from, to) => {
  const w = WK[id];
  if (!w || !w.length) return {f:0,t:0,a:0,o:0};
  const filtered = w.filter(d => d.iso >= from && d.iso <= to);
  return filtered.reduce((acc, d) => ({f:acc.f+d.f, t:acc.t+d.t, a:acc.a+d.a, o:acc.o+d.o}), {f:0,t:0,a:0,o:0});
};

const searchText = (item) => [item.query, item.art, item.nm, item.ww, item.campaign, item.model, item.channel].filter(Boolean).join(' ').toLowerCase();

// ======== PROMO CODES ⇄ SUPABASE ==========================

const PROMOS = [
  { id:1, code:'CHARLOTTE10', channel:'Соцсети', discount:10, from:null, until:null, status:'active', qty:8, sales:12433, updated:'27.04' },
  { id:2, code:'OOOCORP25', channel:'Корп', discount:25, from:null, until:null, status:'active', qty:1, sales:696, updated:'27.04' },
  { id:3, code:'UFL6BFH9_AUDREY_TG10', channel:'Блогер', discount:10, from:null, until:null, status:'active', qty:1, sales:2295, updated:'27.04' },
  { id:4, code:'MYBELLA5', channel:'ООО', discount:5, from:null, until:null, status:'active', qty:0, sales:0, updated:'27.04' },
  { id:5, code:'AUDREY_fadeewa_TG10', channel:'ООО', discount:10, from:null, until:null, status:'active', qty:0, sales:0, updated:'27.04' },
  { id:6, code:'LANA5', channel:'ООО', discount:5, from:null, until:null, status:'active', qty:0, sales:0, updated:'27.04' },
  { id:8, code:'WB:050B58B0-04F5-423C-9DA7', channel:null, discount:null, from:null, until:null, status:'unidentified', qty:1, sales:1702, updated:'27.04' },
];
const PROMO_W = { 1:[{week:'02 мар',orders:7,sales:10845,returns:0},{week:'09 мар',orders:1,sales:1588,returns:0}], 2:[{week:'23 мар',orders:1,sales:696,returns:0}], 3:[{week:'06 апр',orders:1,sales:2295,returns:0}], 8:[{week:'27 апр',orders:1,sales:1702,returns:0}] };
const PROMO_PROD = { 1:[{sku:'Wendy/dark_beige/S',model:'Wendy',qty:4,amt:6240},{sku:'Audrey/nude/M',model:'Audrey',qty:2,amt:3100},{sku:'Vuki/чёрный/S',model:'Vuki',qty:2,amt:3093}], 2:[{sku:'Moon/lavender/S',model:'Moon',qty:1,amt:696}], 3:[{sku:'Audrey/dusty_rose/M',model:'Audrey',qty:1,amt:2295}], 8:[{sku:'Неизвестный',model:'—',qty:1,amt:1702}] };
const PROMO_CH = ['Соцсети','Блогер','Корп','ЯПС','ООО','другое'];

// ======== ATOMS ============================================

function Badge({color,label,compact}) {
  const m={green:'bg-emerald-50 text-emerald-700 ring-emerald-600/20',blue:'bg-blue-50 text-blue-700 ring-blue-600/20',amber:'bg-amber-50 text-amber-700 ring-amber-600/20',gray:'bg-stone-100 text-stone-600 ring-stone-500/20'};
  const d={green:'bg-emerald-500',blue:'bg-blue-500',amber:'bg-amber-500',gray:'bg-stone-400'};
  return <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium ring-1 ring-inset ${m[color]||m.gray}`}>{!compact&&<span className={`w-1.5 h-1.5 rounded-full shrink-0 ${d[color]||d.gray}`}/>}{label}</span>;
}
function KPI({label,value,sub}) { return <div className="bg-white rounded-lg border border-stone-200 px-4 py-3"><div className="text-[11px] uppercase tracking-wider text-stone-400 font-medium">{label}</div><div className="text-xl font-medium text-stone-900 tabular-nums leading-tight mt-0.5">{value}</div>{sub&&<div className="text-[10px] text-stone-400 mt-0.5">{sub}</div>}</div>; }
function Empty({text}) { return <div className="py-6 flex flex-col items-center gap-2"><Clock className="w-4 h-4 text-stone-300"/><p className="text-xs text-stone-400 italic">{text}</p></div>; }

const TH  = "px-2 py-2 text-left text-[10px] uppercase tracking-wider text-stone-400 font-medium select-none whitespace-nowrap";
const THR = "px-2 py-2 text-right text-[10px] uppercase tracking-wider text-stone-400 font-medium select-none whitespace-nowrap";
const iCls = "w-full border border-stone-200 rounded-md px-2.5 py-1.5 text-sm text-stone-900 focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 bg-white";
const lCls = "block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1";
const dateInputCls = "border border-stone-200 rounded-md px-2 py-1 text-xs tabular-nums text-stone-700 focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 bg-white w-[120px]";

// ======== SELECT MENU (custom dropdown) ====================

function SelectMenu({ label, value, options, onChange, allowAdd, placeholder='Выбрать…' }) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [adding, setAdding] = useState(false);
  const [newVal, setNewVal] = useState('');
  const ref = React.useRef(null);

  // Close on outside click
  React.useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setAdding(false); setFilter(''); } };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const opts = (typeof options[0] === 'string' ? options.map(o => ({ value: o, label: o })) : options);
  const filtered = filter ? opts.filter(o => o.label.toLowerCase().includes(filter.toLowerCase())) : opts;
  const current = opts.find(o => o.value === value);

  const handleAdd = () => {
    if (newVal.trim()) {
      onChange(newVal.trim());
      setNewVal('');
      setAdding(false);
      setOpen(false);
      setFilter('');
    }
  };

  return (
    <div className="relative" ref={ref}>
      {label && <div className={lCls}>{label}</div>}
      <button type="button" onClick={() => { setOpen(!open); setFilter(''); setAdding(false); }}
        className="w-full flex items-center justify-between border border-stone-200 rounded-md px-2.5 py-1.5 text-sm text-left bg-white hover:border-stone-300 focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 transition-colors">
        <span className={current ? 'text-stone-900' : 'text-stone-400'}>{current ? current.label : placeholder}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-stone-400 transition-transform ${open ? 'rotate-180' : ''}`}/>
      </button>
      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-40 bg-white border border-stone-200 rounded-lg shadow-sm overflow-hidden">
          {opts.length > 5 && (
            <div className="p-1.5 border-b border-stone-100">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-stone-400"/>
                <input autoFocus value={filter} onChange={e => setFilter(e.target.value)} placeholder="Поиск…"
                  className="w-full pl-7 pr-2 py-1 text-xs border border-stone-100 rounded focus:outline-none focus:border-stone-300 bg-stone-50"/>
              </div>
            </div>
          )}
          <div className="max-h-[200px] overflow-y-auto py-1">
            {/* Empty option */}
            <button onClick={() => { onChange(''); setOpen(false); setFilter(''); }}
              className="w-full flex items-center px-3 py-1.5 text-sm text-stone-400 hover:bg-stone-50 text-left">—</button>
            {filtered.map(o => (
              <button key={o.value} onClick={() => { onChange(o.value); setOpen(false); setFilter(''); }}
                className={`w-full flex items-center justify-between px-3 py-1.5 text-sm hover:bg-stone-50 text-left transition-colors ${o.value === value ? 'bg-stone-50 text-stone-900 font-medium' : 'text-stone-700'}`}>
                <span className="truncate">{o.label}</span>
                {o.value === value && <Check className="w-3 h-3 text-emerald-600 shrink-0 ml-2"/>}
              </button>
            ))}
            {filter && filtered.length === 0 && (
              <div className="px-3 py-2 text-xs text-stone-400 italic">Ничего не найдено</div>
            )}
          </div>
          {allowAdd && (
            <div className="border-t border-stone-100 p-1.5">
              {adding ? (
                <div className="flex items-center gap-1">
                  <input autoFocus value={newVal} onChange={e => setNewVal(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleAdd()}
                    placeholder="Новое значение…" className="flex-1 px-2 py-1 text-xs border border-stone-200 rounded focus:outline-none focus:border-stone-900 bg-white"/>
                  <button onClick={handleAdd} disabled={!newVal.trim()} className="p-1 rounded text-emerald-600 hover:bg-emerald-50 disabled:opacity-30"><Check className="w-3.5 h-3.5"/></button>
                  <button onClick={() => { setAdding(false); setNewVal(''); }} className="p-1 rounded text-stone-400 hover:bg-stone-100"><X className="w-3.5 h-3.5"/></button>
                </div>
              ) : (
                <button onClick={() => setAdding(true)} className="w-full flex items-center gap-1.5 px-2 py-1 text-xs text-stone-500 hover:text-stone-700 hover:bg-stone-50 rounded transition-colors">
                  <Plus className="w-3 h-3"/>Добавить новый
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ======== DATE RANGE PICKER ================================

function DateRange({ from, to, onChange }) {
  return (
    <div className="flex items-center gap-1.5">
      <Calendar className="w-3.5 h-3.5 text-stone-400 shrink-0"/>
      <input type="date" value={from} min={FIRST_DATE} max={to} onChange={e=>onChange(e.target.value,to)} className={dateInputCls}/>
      <span className="text-stone-300 text-xs">—</span>
      <input type="date" value={to} min={from} max={LAST_DATE} onChange={e=>onChange(from,e.target.value)} className={dateInputCls}/>
    </div>
  );
}

// ======== UPDATE STATUS BAR ================================

function UpdateBar() {
  const [syncing, setSyncing] = useState(false);
  const handleSync = () => { setSyncing(true); setTimeout(()=>setSyncing(false), 2000); };
  return (
    <div className="flex items-center gap-3 px-6 py-1.5 bg-stone-50 border-b border-stone-200 text-[11px]">
      <div className="flex items-center gap-1.5 text-stone-500">
        <CheckCircle className="w-3 h-3 text-emerald-500"/>
        <span className="tabular-nums">27 апр 2026, 23:24 МСК</span>
        <span className="text-stone-300">·</span>
        <span className="text-emerald-600">✓ 1 нед (20.04–26.04), пропусков нет</span>
      </div>
      <button onClick={handleSync} disabled={syncing}
        className={`ml-auto flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium transition-colors ${syncing ? 'border-stone-200 text-stone-400 bg-stone-100' : 'border-stone-300 text-stone-600 hover:bg-stone-100 hover:border-stone-400'}`}>
        <RefreshCw className={`w-3 h-3 ${syncing?'animate-spin':''}`}/>{syncing?'Обновляю…':'Обновить'}
      </button>
    </div>
  );
}

// ======== SECTION HEADER ===================================

function SectionHeader({ group, count, collapsed, onToggle }) {
  return (
    <tr className="bg-stone-50/80 border-y border-stone-200 cursor-pointer select-none hover:bg-stone-100/60 transition-colors" onClick={onToggle}>
      <td colSpan={12} className="px-3 py-2">
        <div className="flex items-center gap-2">
          {collapsed ? <ChevronRight className="w-3.5 h-3.5 text-stone-400"/> : <ChevronDown className="w-3.5 h-3.5 text-stone-400"/>}
          <span className="text-[12px] font-medium text-stone-700">{group.icon} {group.label}</span>
          <span className="text-[11px] tabular-nums text-stone-400">{count}</span>
        </div>
      </td>
    </tr>
  );
}

// ======== STATUS EDITOR (в стиле дизайн-системы) ===========

function StatusEditor({ status, onChange }) {
  const [open, setOpen] = useState(false);
  const ws = WS[status];
  return (
    <div className="relative">
      <button onClick={()=>setOpen(!open)} className="group flex items-center gap-1.5 px-2 py-1 rounded-md border border-transparent hover:border-stone-200 transition-colors">
        <Badge color={ws.color} label={ws.label} />
        <ChevronDown className="w-3 h-3 text-stone-300 group-hover:text-stone-500"/>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-30 bg-white border border-stone-200 rounded-lg shadow-sm py-1 min-w-[150px]">
          {Object.entries(WS).map(([k,v]) => (
            <button key={k} onClick={()=>{onChange(k);setOpen(false);}}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-stone-50 transition-colors ${k===status?'bg-stone-50':''}`}>
              <Badge color={v.color} label={v.label} compact/>
              {k===status&&<Check className="w-3 h-3 text-emerald-600 ml-auto"/>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ======== SEARCH DETAIL PANEL ==============================

function SQPanel({ item, onClose, dateFrom, dateTo }) {
  const [showAll, setShowAll] = useState(false);
  const [status, setStatus] = useState(item.status);
  const weekly = WK[item.id] || [];
  const rangeWeeks = weekly.filter(d => d.iso >= dateFrom && d.iso <= dateTo);
  const total = aggRange(item.id, dateFrom, dateTo);
  const allTotal = aggRange(item.id, FIRST_DATE, LAST_DATE);
  const sliced = showAll ? weekly : rangeWeeks;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between px-5 py-4 border-b border-stone-200">
        <div className="flex-1 min-w-0 mr-3">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="font-mono text-sm text-stone-900 font-medium">{item.query}</span>
            <StatusEditor status={status} onChange={setStatus}/>
          </div>
          {item.art && <div className="text-xs text-stone-500 mb-1">{item.art}</div>}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-[11px] font-medium ring-1 ring-inset ring-stone-500/20">{item.channel}</span>
            {item.campaign&&<span className="text-[11px] text-stone-500">{item.campaign}</span>}
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100"><X className="w-3.5 h-3.5"/></button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {item.nm&&(
          <div className="px-5 py-3 border-b border-stone-200 bg-stone-50/40">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
              <span className="text-stone-400">Номенклатура</span><span className="font-mono text-stone-700 text-right">{item.nm}</span>
              {item.ww&&<><span className="text-stone-400">WW-код</span><span className="font-mono text-stone-700 text-right">{item.ww}</span></>}
              {item.art&&<><span className="text-stone-400">Артикул</span><span className="text-stone-700 text-right">{item.art}</span></>}
              {item.model&&<><span className="text-stone-400">Модель</span><span className="text-stone-700 text-right">{item.model}</span></>}
            </div>
          </div>
        )}

        {/* Воронка за выбранный период */}
        <div className="px-5 py-4 border-b border-stone-200">
          <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-3">За выбранный период</div>
          <div className="space-y-2">
            <div className="flex items-center justify-between"><span className="text-xs text-stone-500">Частота</span><span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(total.f)}</span></div>
            <div className="flex items-center justify-between"><span className="text-xs text-stone-500">Переходы</span><span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(total.t)}</span></div>
            <div className="flex items-center justify-between pl-4 -mt-0.5"><span className="text-[11px] text-stone-400">CR перех → корзина</span><span className="text-[11px] text-stone-500 tabular-nums">{pct(total.a, total.t)}</span></div>
            <div className="flex items-center justify-between"><span className="text-xs text-stone-500">Корзина</span><span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(total.a)}</span></div>
            <div className="flex items-center justify-between pl-4 -mt-0.5"><span className="text-[11px] text-stone-400">CR корзина → заказ</span><span className="text-[11px] text-stone-500 tabular-nums">{pct(total.o, total.a)}</span></div>
            <div className="flex items-center justify-between"><span className="text-xs text-stone-500">Заказы</span><span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(total.o)}</span></div>
            <div className="pt-1 mt-1 border-t border-stone-100 flex items-center justify-between">
              <span className="text-xs font-medium text-stone-700">CR перех → заказ</span>
              <span className="text-sm font-medium text-stone-900 tabular-nums">{pct(total.o, total.t)}</span>
            </div>
          </div>
          <div className="text-[10px] text-stone-400 mt-3">Всего за всё время: {fmt(allTotal.o)} заказов · {weekly.length} нед данных</div>
        </div>

        {/* Weekly table */}
        <div className="px-5 py-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[11px] uppercase tracking-wider text-stone-400">{showAll?'Все недели':'За период'}</div>
            <button onClick={()=>setShowAll(!showAll)} className="text-[11px] text-stone-500 hover:text-stone-700 underline">{showAll?`За период (${rangeWeeks.length})`:`Все ${weekly.length}`}</button>
          </div>
          {sliced.length>0?(
            <div className="overflow-y-auto max-h-[280px]"><table className="w-full text-xs"><thead className="sticky top-0 bg-stone-50/90 backdrop-blur-sm"><tr className="border-b border-stone-200">
              <th className="px-1 py-1 text-left text-[10px] uppercase text-stone-400">Нед</th>
              <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Част.</th>
              <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Перех.</th>
              <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Корз.</th>
              <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Зак.</th>
              <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">CRV</th>
            </tr></thead><tbody className="divide-y divide-stone-50">
              {sliced.map((w,i)=><tr key={i} className="hover:bg-stone-50/60">
                <td className="px-1 py-1 tabular-nums text-stone-500">{w.week}</td>
                <td className="px-1 py-1 text-right tabular-nums text-stone-600">{fmt(w.f)}</td>
                <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(w.t)}</td>
                <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(w.a)}</td>
                <td className="px-1 py-1 text-right tabular-nums text-stone-900 font-medium">{fmt(w.o)}</td>
                <td className="px-1 py-1 text-right tabular-nums text-stone-400">{pct(w.o,w.t)}</td>
              </tr>)}
            </tbody></table></div>
          ):<Empty text="Нет данных за этот период"/>}
        </div>
      </div>
    </div>
  );
}

function AddWWPanel({ onClose }) {
  const [model,setModel]=useState('');const [color,setColor]=useState('');const [size,setSize]=useState('');const [channel,setChannel]=useState('');const [ww,setWw]=useState('');const [campaign,setCampaign]=useState('');
  const [channels] = useState(['Яндекс','Таргет ВК','Adblogger','креаторы','SMM']);
  const [campaigns] = useState(['WENDY_креаторы','AUDREY_креатор','VUKI_креаторы','MOON_креаторы','RUBY_креаторы','Яндекс промост']);
  const colors=model?COLORS_BY[model]||[]:[];const matched=model&&color&&size?SKUS.find(s=>s.model===model&&s.color===color&&s.size===size):null;
  return(
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200"><div className="text-sm font-medium text-stone-900">Новый WW-код</div><button onClick={onClose} className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100"><X className="w-3.5 h-3.5"/></button></div>
      <div className="px-5 py-4 space-y-3 overflow-y-auto">
        <SelectMenu label="Модель" value={model} placeholder="Выбрать модель…"
          options={MODELS.map(m=>({value:m.code,label:m.code}))}
          onChange={v=>{setModel(v);setColor('');setSize('');}} />
        {model&&<SelectMenu label="Цвет" value={color} placeholder="Выбрать цвет…"
          options={colors.map(c=>({value:c,label:c}))}
          onChange={v=>{setColor(v);setSize('');}} />}
        {color&&<SelectMenu label="Размер" value={size} placeholder="Выбрать размер…"
          options={SIZES.map(s=>({value:s,label:s}))}
          onChange={setSize} />}
        {matched&&<div className="bg-stone-50 rounded-md border border-stone-100 px-3 py-2"><div className="text-[10px] uppercase text-stone-400">Привязан</div><div className="text-sm text-stone-900 mt-0.5">{skuLabel(matched)}</div><div className="text-[11px] font-mono text-stone-500">NM: {matched.nm}</div></div>}
        {!matched&&model&&color&&size&&<div className="bg-amber-50 rounded-md border border-amber-200 px-3 py-2 text-[11px] text-amber-700">SKU не найден</div>}
        <div><label className={lCls}>WW-код</label><input className={`${iCls} font-mono uppercase`} value={ww} placeholder="WW..." onChange={e=>setWw(e.target.value)}/></div>
        <SelectMenu label="Канал" value={channel} placeholder="Выбрать канал…"
          options={channels} onChange={setChannel} allowAdd />
        <SelectMenu label="Кампания / блогер" value={campaign} placeholder="Опционально…"
          options={campaigns} onChange={setCampaign} allowAdd />
        <button disabled={!matched||!ww||!channel} className="w-full py-1.5 rounded-md bg-stone-900 text-white text-sm font-medium hover:bg-stone-800 disabled:opacity-30 disabled:cursor-not-allowed">Добавить</button>
      </div>
    </div>
  );
}

// ======== SEARCH PAGE ======================================

function SearchPage() {
  const [selId,setSelId]=useState(null);
  const [panel,setPanel]=useState('closed');
  const [modelF,setModelF]=useState('all');
  const [channelF,setChannelF]=useState('all');
  const [dateFrom,setDateFrom]=useState(DEFAULT_FROM);
  const [dateTo,setDateTo]=useState(DEFAULT_TO);
  const [search,setSearch]=useState('');
  const [collapsed,setCollapsed]=useState({});

  const toggle = g => setCollapsed(c=>({...c,[g]:!c[g]}));
  const open = panel!=='closed';
  const selected = ITEMS.find(i=>i.id===selId);

  const uniqueModels = useMemo(()=>[...new Set(ITEMS.map(i=>i.model).filter(Boolean))].sort(),[]);
  const uniqueChannels = useMemo(()=>[...new Set(ITEMS.map(i=>i.channel))].sort(),[]);

  const filtered = useMemo(()=>{
    let list = ITEMS.slice();
    if (modelF !== 'all') list = list.filter(i => i.model === modelF);
    if (channelF !== 'all') list = list.filter(i => i.channel === channelF);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(i => searchText(i).includes(q));
    }
    return list;
  },[modelF,channelF,search]);

  const grouped = useMemo(()=>{
    const result = {};
    GROUPS.forEach(g=>{
      result[g.id] = filtered
        .filter(i => i.group === g.id)
        .sort((a,b) => aggRange(b.id,dateFrom,dateTo).o - aggRange(a.id,dateFrom,dateTo).o);
    });
    return result;
  },[filtered,dateFrom,dateTo]);

  // Summary totals
  const totals = useMemo(()=>{
    return filtered.reduce((acc, item) => {
      const a = aggRange(item.id, dateFrom, dateTo);
      return { f:acc.f+a.f, t:acc.t+a.t, a:acc.a+a.a, o:acc.o+a.o };
    }, {f:0,t:0,a:0,o:0});
  },[filtered,dateFrom,dateTo]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 pt-5 pb-4 border-b border-stone-200 bg-white">
        <div className="flex items-end justify-between">
          <div>
            <h1 style={{fontFamily:"'Instrument Serif',serif",fontSize:24,fontStyle:'italic'}} className="text-stone-900">Поисковые запросы</h1>
            <p className="text-sm text-stone-500 mt-0.5">Брендовые, артикулы и подменные WW-коды</p>
          </div>
          <button onClick={()=>{setSelId(null);setPanel('add');}} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-stone-900 text-white text-sm font-medium hover:bg-stone-800"><Plus className="w-3.5 h-3.5"/>Добавить WW-код</button>
        </div>
        <div className="flex items-center gap-1.5 mt-3 flex-wrap">
          <span className="text-[11px] text-stone-400 mr-0.5">Модель:</span>
          {['all',...uniqueModels].map(m=>(
            <button key={m} onClick={()=>setModelF(m)} className={`px-2.5 py-1 rounded-full text-[12px] font-medium transition-colors ${modelF===m?'bg-stone-900 text-white':'bg-stone-100 text-stone-600 hover:bg-stone-200'}`}>{m==='all'?'Все':m}</button>
          ))}
        </div>
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          <span className="text-[11px] text-stone-400 mr-0.5">Канал:</span>
          {['all',...uniqueChannels].map(c=>(
            <button key={c} onClick={()=>setChannelF(c)} className={`px-2.5 py-1 rounded-full text-[12px] font-medium transition-colors ${channelF===c?'bg-stone-900 text-white':'bg-stone-100 text-stone-600 hover:bg-stone-200'}`}>
              {c==='all'?'Все':c}
              {c!=='all'&&<span className="ml-1 text-[10px] opacity-60 tabular-nums">{ITEMS.filter(i=>i.channel===c).length}</span>}
            </button>
          ))}
        </div>
      </div>

      <UpdateBar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <div className="px-6 py-2 border-b border-stone-200 flex items-center gap-3 bg-white flex-wrap">
            <div className="relative flex-1 min-w-[180px] max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400"/>
              <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Запрос, артикул, WW-код, кампания..."
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"/>
            </div>
            <DateRange from={dateFrom} to={dateTo} onChange={(f,t)=>{setDateFrom(f);setDateTo(t);}}/>
            <span className="text-[10px] text-stone-400 ml-auto tabular-nums">{filtered.length} записей</span>
          </div>

          <div className="flex-1 overflow-auto">
            <table className="w-full">
              <thead className="sticky top-0 bg-stone-50/95 border-b border-stone-200 backdrop-blur-sm z-20">
                <tr>
                  <th className={TH} style={{minWidth:110}}>Запрос</th>
                  <th className={TH}>Артикул</th>
                  <th className={TH}>Канал</th>
                  <th className={TH}>Кампания</th>
                  <th className={THR}>Частота</th>
                  <th className={THR}>Перех.</th>
                  <th className={THR}>CR→корз</th>
                  <th className={THR}>Корз.</th>
                  <th className={THR}>CR→зак</th>
                  <th className={THR}>Заказы</th>
                  <th className={THR}>CRV</th>
                </tr>
              </thead>
              <tbody>
                {GROUPS.map(g => {
                  const items = grouped[g.id];
                  if (!items || items.length === 0) return null;
                  const isCol = collapsed[g.id];
                  return (
                    <React.Fragment key={g.id}>
                      <SectionHeader group={g} count={items.length} collapsed={isCol} onToggle={()=>toggle(g.id)} />
                      {!isCol && items.map(item => {
                        const a = aggRange(item.id, dateFrom, dateTo);
                        const sel = item.id===selId;
                        return (
                          <tr key={item.id} onClick={()=>{setSelId(item.id);setPanel('detail');}}
                            className={`cursor-pointer transition-colors border-b border-stone-50 ${sel?'bg-stone-50':'hover:bg-stone-50/60'}`}>
                            <td className="px-2 py-2"><span className="font-mono text-xs text-stone-900">{item.query}</span></td>
                            <td className="px-2 py-2 text-xs text-stone-500 truncate max-w-[130px]">{item.art||''}</td>
                            <td className="px-2 py-2"><span className="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-[10px] font-medium ring-1 ring-inset ring-stone-500/20">{item.channel}</span></td>
                            <td className="px-2 py-2 text-xs text-stone-500 truncate max-w-[100px]">{item.campaign||''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-sm text-stone-600">{a.f>0?fmt(a.f):''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-sm text-stone-600">{a.t>0?fmt(a.t):''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-[11px] text-stone-400">{a.t>0?pct(a.a,a.t):''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-sm text-stone-600">{a.a>0?fmt(a.a):''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-[11px] text-stone-400">{a.a>0?pct(a.o,a.a):''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-sm text-stone-900 font-medium">{a.o>0?fmt(a.o):''}</td>
                            <td className="px-2 py-2 text-right tabular-nums text-[11px] font-medium text-stone-700">{a.t>0?pct(a.o,a.t):''}</td>
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  );
                })}
              </tbody>
              <tfoot className="sticky bottom-0 bg-stone-100/95 backdrop-blur-sm border-t-2 border-stone-300 z-10">
                <tr>
                  <td className="px-2 py-2 text-xs font-medium text-stone-700" colSpan={4}>Итого · {filtered.length} запросов</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-stone-900">{fmt(totals.f)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-stone-900">{fmt(totals.t)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[11px] font-medium text-stone-600">{pct(totals.a,totals.t)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-stone-900">{fmt(totals.a)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[11px] font-medium text-stone-600">{pct(totals.o,totals.a)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-stone-900">{fmt(totals.o)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-[11px] font-bold text-stone-900">{pct(totals.o,totals.t)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {open&&<div className="w-[420px] shrink-0 border-l border-stone-200 bg-white flex flex-col h-full overflow-hidden">
          {panel==='add'?<AddWWPanel onClose={()=>setPanel('closed')}/>:selected&&<SQPanel item={selected} onClose={()=>{setSelId(null);setPanel('closed');}} dateFrom={dateFrom} dateTo={dateTo}/>}
        </div>}
      </div>
    </div>
  );
}

// ======== PROMO DETAIL =====================================

function PromoPanel({promo,onClose,mode}) {
  const [edit,setEdit]=useState(mode==='add');
  const [form,setForm]=useState(mode==='add'?{code:'',channel:'',discount:'',from:'',until:''}:{code:promo.code,channel:promo.channel||'',discount:promo.discount||'',from:promo.from||'',until:promo.until||''});
  const weekly=promo?PROMO_W[promo.id]||[]:[];const products=promo?PROMO_PROD[promo.id]||[]:[];
  const st=promo?(promo.status==='unidentified'?{l:'Не идентиф.',c:'amber'}:promo.qty===0?{l:'Нет данных',c:'gray'}:{l:'Активен',c:'green'}):null;
  const avg = promo&&promo.qty>0 ? Math.round(promo.sales/promo.qty) : 0;
  return(
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between px-5 py-4 border-b border-stone-200">
        <div className="flex-1 min-w-0 mr-3">{mode==='add'?<div className="text-sm font-medium text-stone-900">Новый промокод</div>:(<><div className="font-mono text-xs text-stone-400 mb-1 break-all">{promo.code}</div><div className="flex items-center gap-1.5"><Badge color={st.c} label={st.l}/>{promo.channel&&<span className="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-[11px] font-medium ring-1 ring-inset ring-stone-500/20">{promo.channel}</span>}</div></>)}</div>
        <div className="flex items-center gap-1 shrink-0">{mode!=='add'&&!edit&&<button onClick={()=>setEdit(true)} className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100"><Edit3 className="w-3.5 h-3.5"/></button>}<button onClick={onClose} className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100"><X className="w-3.5 h-3.5"/></button></div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="px-5 py-4 border-b border-stone-200 space-y-3">
          <div><label className={lCls}>Код</label>{edit?<input className={`${iCls} font-mono uppercase`} value={form.code} onChange={e=>setForm(f=>({...f,code:e.target.value}))}/>:<div className="font-mono text-xs text-stone-900 break-all">{form.code}</div>}</div>
          <div className="grid grid-cols-2 gap-3"><div>{edit?<SelectMenu label="Канал" value={form.channel} placeholder="Выбрать…" options={PROMO_CH} onChange={v=>setForm(f=>({...f,channel:v}))} allowAdd/>:<div><div className={lCls}>Канал</div><div className="text-sm text-stone-900">{form.channel||'—'}</div></div>}</div><div><label className={lCls}>Скидка %</label>{edit?<input className={iCls} type="number" value={form.discount} onChange={e=>setForm(f=>({...f,discount:e.target.value}))}/>:<div className="text-sm tabular-nums text-stone-900">{form.discount?`${form.discount}%`:'—'}</div>}</div></div>
          <div className="grid grid-cols-2 gap-3"><div><label className={lCls}>Начало</label>{edit?<input className={iCls} type="date" value={form.from} onChange={e=>setForm(f=>({...f,from:e.target.value}))}/>:<div className="text-sm tabular-nums text-stone-900">{form.from||'—'}</div>}</div><div><label className={lCls}>Окончание</label>{edit?<input className={iCls} type="date" value={form.until} onChange={e=>setForm(f=>({...f,until:e.target.value}))}/>:<div className="text-sm tabular-nums text-stone-900">{form.until||'—'}</div>}</div></div>
          {edit&&<div className="flex gap-2 pt-1"><button className="flex-1 py-1.5 rounded-md bg-stone-900 text-white text-sm font-medium hover:bg-stone-800">{mode==='add'?'Создать':'Сохранить'}</button>{mode!=='add'&&<button onClick={()=>setEdit(false)} className="py-1.5 px-3 rounded-md border border-stone-200 text-stone-700 text-sm hover:bg-stone-50">Отмена</button>}</div>}
        </div>
        {mode!=='add'&&<>
          <div className="px-5 py-4 border-b border-stone-200">
            <div className="grid grid-cols-3 gap-3">
              <div><div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Продажи, шт</div><div className="text-lg font-medium text-stone-900 tabular-nums">{fmt(promo.qty)}</div></div>
              <div><div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Продажи, ₽</div><div className="text-lg font-medium text-stone-900 tabular-nums">{fmtR(promo.sales)}</div></div>
              <div><div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Ср. чек, ₽</div><div className="text-lg font-medium text-stone-900 tabular-nums">{avg>0?fmtR(avg):'—'}</div></div>
            </div>
          </div>
          {products.length>0&&<div className="px-5 py-4 border-b border-stone-200"><div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">Товарная разбивка</div><table className="w-full text-xs"><thead><tr className="border-b border-stone-100"><th className="text-left py-1 text-[10px] uppercase text-stone-400">Товар</th><th className="text-right py-1 text-[10px] uppercase text-stone-400">Шт</th><th className="text-right py-1 text-[10px] uppercase text-stone-400">Сумма</th></tr></thead><tbody className="divide-y divide-stone-50">{products.map((p,i)=><tr key={i}><td className="py-1.5"><div className="text-stone-900">{p.sku}</div><div className="text-[10px] text-stone-400">{p.model}</div></td><td className="py-1.5 text-right tabular-nums text-stone-700">{p.qty}</td><td className="py-1.5 text-right tabular-nums text-stone-900 font-medium">{fmtR(p.amt)}</td></tr>)}</tbody></table></div>}
          <div className="px-5 py-4"><div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">По неделям</div>{weekly.length>0?<table className="w-full text-xs"><thead><tr className="border-b border-stone-100"><th className="text-left py-1 text-[10px] uppercase text-stone-400">Нед</th><th className="text-right py-1 text-[10px] uppercase text-stone-400">Зак.</th><th className="text-right py-1 text-[10px] uppercase text-stone-400">Продажи</th><th className="text-right py-1 text-[10px] uppercase text-stone-400">Возвр.</th></tr></thead><tbody className="divide-y divide-stone-50">{weekly.map((w,i)=><tr key={i}><td className="py-1.5 tabular-nums text-stone-500">{w.week}</td><td className="py-1.5 text-right tabular-nums text-stone-900 font-medium">{w.orders}</td><td className="py-1.5 text-right tabular-nums text-stone-700">{fmtR(w.sales)}</td><td className="py-1.5 text-right tabular-nums text-stone-400">{w.returns}</td></tr>)}</tbody></table>:<Empty text="Данные после понедельника"/>}</div>
        </>}
      </div>
    </div>
  );
}

// ======== PROMO PAGE =======================================

function PromoPage() {
  const [selId,setSelId]=useState(null);const [panel,setPanel]=useState('closed');const [search,setSearch]=useState('');
  const [dateFrom,setDateFrom]=useState(DEFAULT_FROM);const [dateTo,setDateTo]=useState(DEFAULT_TO);
  const selected=PROMOS.find(p=>p.id===selId);const open=panel!=='closed';
  const filtered=useMemo(()=>{let l=PROMOS.slice();if(search)l=l.filter(p=>p.code.toLowerCase().includes(search.toLowerCase())||p.channel?.toLowerCase().includes(search.toLowerCase()));return l.sort((a,b)=>b.sales-a.sales);},[search]);
  const fQ=filtered.reduce((s,p)=>s+p.qty,0);const fS=filtered.reduce((s,p)=>s+p.sales,0);const fAvg=fQ>0?Math.round(fS/fQ):0;
  const tQ=PROMOS.reduce((s,p)=>s+p.qty,0);const tS=PROMOS.reduce((s,p)=>s+p.sales,0);const tAvg=tQ>0?Math.round(tS/tQ):0;
  return(
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 pt-5 pb-4 border-b border-stone-200 bg-white">
        <div className="flex items-end justify-between"><div><h1 style={{fontFamily:"'Instrument Serif',serif",fontSize:24,fontStyle:'italic'}} className="text-stone-900">Промокоды</h1><p className="text-sm text-stone-500 mt-0.5">Статистика по кодам скидок</p></div><button onClick={()=>{setSelId(null);setPanel('add');}} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-stone-900 text-white text-sm font-medium hover:bg-stone-800"><Plus className="w-3.5 h-3.5"/>Добавить</button></div>
        <div className="grid grid-cols-4 gap-3 mt-4">
          <KPI label="Активных" value={PROMOS.filter(p=>p.status==='active').length} sub={`из ${PROMOS.length}`}/>
          <KPI label="Продажи, шт" value={fmt(tQ)}/>
          <KPI label="Продажи, ₽" value={fmtR(tS)}/>
          <KPI label="Ср. чек, ₽" value={tAvg>0?fmtR(tAvg):'—'}/>
        </div>
      </div>

      <UpdateBar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <div className="px-6 py-2 border-b border-stone-200 flex items-center gap-3 bg-white flex-wrap">
            <div className="relative flex-1 max-w-xs"><Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Код или канал..." className="w-full pl-8 pr-3 py-1.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"/></div>
            <DateRange from={dateFrom} to={dateTo} onChange={(f,t)=>{setDateFrom(f);setDateTo(t);}}/>
            <span className="text-[10px] text-stone-400 ml-auto tabular-nums">{filtered.length} кодов</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            <table className="w-full"><thead className="sticky top-0 bg-stone-50/90 border-b border-stone-200 backdrop-blur-sm"><tr>
              <th className={TH}>Код</th><th className={TH}>Канал</th><th className={TH}>Скидка</th><th className={TH}>Статус</th>
              <th className={THR}>Продажи, шт</th><th className={THR}>Продажи, ₽</th><th className={THR}>Ср. чек, ₽</th>
            </tr></thead>
              <tbody className="divide-y divide-stone-100">{filtered.map(p=>{
                const st=p.status==='unidentified'?{l:'Не идентиф.',c:'amber'}:p.qty===0?{l:'Нет данных',c:'gray'}:{l:'Активен',c:'green'};
                const avg=p.qty>0?Math.round(p.sales/p.qty):0;
                return(<tr key={p.id} onClick={()=>{setSelId(p.id);setPanel('detail');}} className={`cursor-pointer transition-colors ${p.id===selId?'bg-stone-50':'hover:bg-stone-50/60'}`}>
                  <td className="px-2 py-2.5"><span className={`font-mono text-xs ${p.status==='unidentified'?'text-amber-700':'text-stone-900'}`}>{p.code.length>24?p.code.slice(0,24)+'…':p.code}</span></td>
                  <td className="px-2 py-2.5"><span className="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-[11px] font-medium ring-1 ring-inset ring-stone-500/20">{p.channel||'—'}</span></td>
                  <td className="px-2 py-2.5 text-sm tabular-nums text-stone-700">{p.discount!=null?`${p.discount}%`:'—'}</td>
                  <td className="px-2 py-2.5"><Badge color={st.c} label={st.l} compact/></td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-sm font-medium text-stone-900">{p.qty>0?fmt(p.qty):<span className="text-stone-300">—</span>}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-sm text-stone-700">{p.sales>0?fmtR(p.sales):<span className="text-stone-300">—</span>}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-sm text-stone-500">{avg>0?fmtR(avg):<span className="text-stone-300">—</span>}</td>
                </tr>);})}</tbody>
              <tfoot className="sticky bottom-0 bg-stone-100/95 backdrop-blur-sm border-t-2 border-stone-300 z-10">
                <tr>
                  <td className="px-2 py-2 text-xs font-medium text-stone-700" colSpan={4}>Итого · {filtered.length} кодов</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-stone-900">{fmt(fQ)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-stone-900">{fmtR(fS)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-stone-700">{fAvg>0?fmtR(fAvg):'—'}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
        {open&&<div className="w-[400px] shrink-0 border-l border-stone-200 bg-white flex flex-col h-full overflow-hidden">{panel==='add'?<PromoPanel promo={null} onClose={()=>setPanel('closed')} mode="add"/>:selected&&<PromoPanel promo={selected} onClose={()=>{setSelId(null);setPanel('closed');}} mode="view"/>}</div>}
      </div>
    </div>
  );
}

// ======== LAYOUT ===========================================

const NAV=[{id:'dashboard',icon:LayoutDashboard},{id:'catalog',icon:Package},{id:'analytics',icon:BarChart3},{id:'marketing',icon:Megaphone,active:true},{id:'influence',icon:Users},{id:'settings',icon:Settings}];
const SUB=[{id:'promo',icon:Percent,label:'Промокоды'},{id:'search',icon:Hash,label:'Поисковые запросы'}];

export default function App(){
  const [sub,setSub]=useState('search');
  return(<>
    <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');*{box-sizing:border-box;margin:0;padding:0}body{background:#FAFAF9;-webkit-font-smoothing:antialiased}::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#E7E5E4;border-radius:2px}input[type="date"]::-webkit-calendar-picker-indicator{opacity:0.4;cursor:pointer}`}</style>
    <div className="flex h-screen bg-stone-50/40 overflow-hidden" style={{fontFamily:"'DM Sans',system-ui,sans-serif"}}>
      <div className="w-12 shrink-0 flex flex-col items-center py-3 gap-1 bg-white border-r border-stone-200 z-10">
        <div className="w-7 h-7 rounded-md mb-3 flex items-center justify-center" style={{background:'linear-gradient(135deg,#7C3AED,#4F46E5)'}}><span className="text-white text-[10px] font-bold">W</span></div>
        {NAV.map(n=><button key={n.id} className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${n.active?'bg-stone-900 text-white':'text-stone-400 hover:bg-stone-100'}`}><n.icon className="w-4 h-4"/></button>)}
      </div>
      <div className="w-44 shrink-0 flex flex-col border-r border-stone-200 bg-white">
        <div className="px-3 py-3 border-b border-stone-100"><div className="text-[11px] uppercase tracking-wider text-stone-400 font-medium px-1">Маркетинг</div></div>
        <nav className="flex-1 p-2 space-y-0.5">{SUB.map(m=><button key={m.id} onClick={()=>setSub(m.id)} className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors ${sub===m.id?'bg-stone-100 text-stone-900 font-medium':'text-stone-500 hover:bg-stone-50'}`}><m.icon className={`w-3.5 h-3.5 ${sub===m.id?'text-stone-700':'text-stone-400'}`}/><span className="truncate text-left">{m.label}</span></button>)}</nav>
      </div>
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">{sub==='promo'?<PromoPage/>:<SearchPage/>}</div>
    </div>
  </>);
}
