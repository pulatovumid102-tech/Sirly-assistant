<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Biznes jarayonlar</title>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#F7F6F3;--surface:#FFF;--surface2:#F0EEE9;--border:#E4E1D9;
  --text:#1A1916;--muted:#7A7770;
  --green:#1A6B3C;--green-bg:#E8F5EE;--green-border:#A8D5BB;
  --red:#8B1A1A;--red-bg:#FDF0F0;--red-border:#E8AAAA;
  --radius:16px;--radius-sm:10px;--card-w:280px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Manrope',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}

.header{background:var(--surface);border-bottom:1px solid var(--border);padding:0 24px;height:56px;display:flex;align-items:center;justify-content:flex-end;position:sticky;top:0;z-index:50;gap:8px}
.admin-btn{border:1px solid var(--border);background:none;padding:5px 14px;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer;color:var(--muted);font-family:'Manrope',sans-serif;transition:all .15s}
.admin-btn:hover{background:var(--surface2)}
.admin-btn.active{background:var(--text);color:#fff;border-color:var(--text)}

.breadcrumb{padding:14px 24px 0;display:flex;align-items:center;gap:6px;font-size:13px;color:var(--muted);flex-wrap:wrap;min-height:36px}
.breadcrumb-item{cursor:pointer;transition:color .15s}.breadcrumb-item:hover{color:var(--text)}
.breadcrumb-sep{opacity:.4}.breadcrumb-current{color:var(--text);font-weight:500}

.main{padding:24px}
.screen{display:none}.screen.active{display:block}
.page-title{font-size:24px;font-weight:700;letter-spacing:-.5px;margin-bottom:6px}
.page-sub{font-size:14px;color:var(--muted);margin-bottom:28px;line-height:1.5}

/* CARDS GRID — for sections and categories */
.cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:16px}
.nav-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;min-height:120px}
.nav-card:hover{border-color:var(--text);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.nav-card-icon{width:44px;height:44px;border-radius:12px;background:var(--surface2);display:flex;align-items:center;justify-content:center;font-size:20px;margin-bottom:16px}
.nav-card-title{font-size:16px;font-weight:700;margin-bottom:6px}
.nav-card-desc{font-size:13px;color:var(--muted);line-height:1.55;padding-right:20px}
.nav-card-arrow{position:absolute;bottom:20px;right:20px;font-size:18px;opacity:.2;transition:opacity .2s,transform .2s}
.nav-card:hover .nav-card-arrow{opacity:.7;transform:translateX(3px)}
.nav-card-actions{position:absolute;top:12px;right:12px;display:flex;gap:4px;opacity:0;transition:opacity .15s}
.nav-card:hover .nav-card-actions{opacity:1}

/* ADD CARD BTN */
.add-card-btn{background:none;border:1.5px dashed var(--border);border-radius:var(--radius);padding:24px;cursor:pointer;font-size:14px;font-weight:500;color:var(--muted);font-family:'Manrope',sans-serif;transition:all .15s;display:flex;align-items:center;justify-content:center;gap:8px;min-height:120px}
.add-card-btn:hover{border-color:var(--text);color:var(--text);background:var(--surface)}

/* SECTION LIST (flows) */
.section-list-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px;gap:12px}
.search-input{padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:'Manrope',sans-serif;background:var(--surface);color:var(--text);width:220px;transition:border .15s}
.search-input:focus{outline:none;border-color:var(--text)}
.section-list{display:flex;flex-direction:column;gap:10px}
.section-item{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:18px 20px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;transition:all .15s}
.section-item:hover{border-color:var(--text);background:var(--surface2)}
.section-item-left{display:flex;align-items:center;gap:14px}
.section-num{width:30px;height:30px;border-radius:8px;background:var(--surface2);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--muted);flex-shrink:0}
.section-name{font-size:15px;font-weight:600}
.section-chevron{color:var(--muted);font-size:18px}
.section-actions{display:flex;gap:6px;opacity:0;transition:opacity .15s}
.section-item:hover .section-actions{opacity:1}
.no-results{text-align:center;padding:32px;color:var(--muted);font-size:13px}
.add-flow-btn{margin-top:12px;width:100%;padding:14px 20px;border:1.5px dashed var(--border);border-radius:var(--radius-sm);background:none;font-size:14px;font-weight:500;color:var(--muted);cursor:pointer;font-family:'Manrope',sans-serif;transition:all .15s;display:flex;align-items:center;justify-content:center;gap:8px}
.add-flow-btn:hover{border-color:var(--text);color:var(--text);background:var(--surface)}

/* FORMS */
.inline-form{background:var(--surface);border:1.5px dashed var(--border);border-radius:var(--radius-sm);padding:16px;margin-top:8px}
.inline-form-title{font-size:13px;font-weight:600;margin-bottom:12px}
.form-row{margin-bottom:10px}
.fi{width:100%;padding:8px 11px;border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:'Manrope',sans-serif;background:var(--bg);color:var(--text);transition:border .15s}
.fi:focus{outline:none;border-color:var(--text)}
.form-label{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;display:block}
.form-actions{display:flex;gap:8px;margin-top:12px}
.btn-save{background:var(--text);color:#fff;border:none;padding:7px 18px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:'Manrope',sans-serif}
.btn-save:hover{opacity:.85}
.btn-cancel{background:none;border:1px solid var(--border);padding:7px 14px;border-radius:8px;font-size:13px;cursor:pointer;color:var(--muted);font-family:'Manrope',sans-serif}
.btn-cancel:hover{background:var(--surface2)}
.btn-sm{border:1px solid var(--border);background:none;border-radius:6px;padding:3px 8px;font-size:11px;cursor:pointer;font-family:'Manrope',sans-serif;color:var(--muted);transition:all .15s}
.btn-sm:hover{background:var(--surface2);color:var(--text)}
.btn-sm-danger{border:1px solid var(--red-border);background:none;border-radius:6px;padding:3px 8px;font-size:11px;cursor:pointer;font-family:'Manrope',sans-serif;color:var(--red)}
.btn-sm-danger:hover{background:var(--red-bg)}

/* TREE */
.flow-tree{overflow-x:auto;padding-bottom:24px}
.tree-col{display:flex;flex-direction:column;gap:0;flex-shrink:0}
.node-row{display:flex;flex-direction:row;align-items:flex-start;gap:0;margin-bottom:16px}
.node-card{width:var(--card-w);flex-shrink:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 14px 12px;position:relative;transition:border .15s}
.node-card:hover{border-color:var(--muted)}
.node-num{position:absolute;top:-1px;left:-1px;width:28px;height:28px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius-sm) 0 var(--radius-sm) 0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--muted)}
.node-name{font-size:13px;font-weight:600;line-height:1.4;margin-top:16px;margin-bottom:3px;padding-right:48px}
.node-desc{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:4px}
.node-msg-wrap{position:relative;margin-top:8px}
.node-msg{background:var(--bg);border-left:2px solid var(--border);border-radius:0 6px 6px 0;padding:8px 32px 8px 10px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text);line-height:1.6;white-space:pre-wrap}
.node-link{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:11px;color:var(--muted);word-break:break-all}
.node-link a{color:var(--text);text-decoration:underline}
.node-corner{position:absolute;top:6px;right:6px;display:flex;gap:3px}
.corner-btn{width:22px;height:22px;border-radius:5px;border:1px solid var(--border);background:var(--surface);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--muted);transition:all .15s;opacity:0}
.node-card:hover .corner-btn{opacity:1}
.corner-btn:hover{border-color:var(--text);color:var(--text)}
.corner-btn.danger:hover{border-color:var(--red);color:var(--red);background:var(--red-bg)}
.corner-btn.link-btn{opacity:1!important;color:var(--text)}
.children-connector{display:flex;flex-direction:row;align-items:stretch}
.v-bar-wrap{display:flex;flex-direction:column;align-items:center;width:32px;flex-shrink:0}
.v-bar{width:1px;background:var(--border);flex:1;margin:0 auto}
.children-col{display:flex;flex-direction:column;gap:0}
.child-row{display:flex;flex-direction:row;align-items:flex-start}
.child-h-line{width:32px;height:1px;background:var(--border);flex-shrink:0;margin-top:27px}
.add-child-btn{width:var(--card-w);padding:9px 12px;border:1.5px dashed var(--border);border-radius:var(--radius-sm);background:none;font-size:12px;color:var(--muted);cursor:pointer;font-family:'Manrope',sans-serif;transition:all .15s;text-align:left;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.add-child-btn:hover{border-color:var(--text);color:var(--text);background:var(--surface)}
.add-root-btn{padding:12px 16px;border:1.5px dashed var(--border);border-radius:var(--radius-sm);background:none;font-size:13px;font-weight:500;color:var(--muted);cursor:pointer;font-family:'Manrope',sans-serif;transition:all .15s;display:flex;align-items:center;gap:8px;margin-top:8px}
.add-root-btn:hover{border-color:var(--text);color:var(--text);background:var(--surface)}

/* IMAGE MODAL */
.img-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:300;align-items:center;justify-content:center;cursor:zoom-out}
.img-modal.open{display:flex}
.img-modal img{max-width:90vw;max-height:90vh;border-radius:8px;object-fit:contain}
/* DRAG */
.section-item.dragging{opacity:.4;border:1.5px dashed var(--text)}
.section-item.drag-over{border-color:var(--text);background:var(--surface2)}
.drag-handle{cursor:grab;color:var(--muted);padding:0 6px;font-size:14px;flex-shrink:0;user-select:none}
.drag-handle:active{cursor:grabbing}
/* TYPE SELECT */
.type-select-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.type-select-btn{padding:14px;border:1.5px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);cursor:pointer;text-align:center;transition:all .15s;font-family:"Manrope",sans-serif;width:100%}
.type-select-btn:hover{border-color:var(--text)}
.type-select-btn.selected{border-color:var(--text);background:var(--surface2)}
.type-icon{font-size:22px;margin-bottom:4px}
.type-name{font-size:13px;font-weight:600}
.type-desc{font-size:11px;color:var(--muted);margin-top:2px}
.back-btn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--surface);border-radius:8px;padding:6px 14px;font-size:13px;font-weight:500;cursor:pointer;color:var(--text);font-family:'Manrope',sans-serif;margin-bottom:20px;transition:all .15s}
.back-btn:hover{background:var(--surface2)}
.progress-bar{background:var(--border);border-radius:4px;height:3px;margin-bottom:24px;overflow:hidden}
.progress-fill{height:100%;background:var(--text);border-radius:4px;transition:width .4s ease}

.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.25);z-index:200;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal-box{background:var(--surface);border-radius:var(--radius);border:1px solid var(--border);padding:28px;width:340px;box-shadow:0 16px 48px rgba(0,0,0,.12)}
.modal-title{font-size:17px;font-weight:700;margin-bottom:4px}
.modal-sub{font-size:13px;color:var(--muted);margin-bottom:20px}
.modal-error{font-size:12px;color:var(--red);margin-top:8px;display:none}
.modal-error.show{display:block}

.notification{position:fixed;bottom:24px;right:24px;background:var(--text);color:#fff;padding:12px 20px;border-radius:10px;font-size:13px;font-weight:500;z-index:999;opacity:0;transform:translateY(8px);transition:all .3s;pointer-events:none}
.notification.show{opacity:1;transform:translateY(0)}
.fade-in{animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:600px){.main{padding:16px}.page-title{font-size:20px}.header{padding:0 16px}:root{--card-w:220px}}
</style>
</head>
<body>

<div class="header">
  <button class="admin-btn" id="exportBtn" onclick="exportData()" style="display:none">⬇ Saqlash</button>
  <button class="admin-btn" id="adminBtn" onclick="handleAdminBtn()">⚙ Admin</button>
</div>
<div class="breadcrumb" id="breadcrumb"></div>
<div class="main">

  <!-- SCREEN: HOME (bo'limlar) -->
  <div class="screen active" id="screen-home">
    <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
    <div class="page-title">Biznes jarayonlar</div>
    <div class="page-sub">Bo'limni tanlang</div>
    <div class="cards-grid" id="sectionsGrid"></div>
    <div id="addSectionFormWrap"></div>
  </div>

  <!-- SCREEN: SECTION (kategoriyalar) -->
  <div class="screen" id="screen-section">
    <button class="back-btn" onclick="goBack('home')">← Orqaga</button>
    <div class="section-list-header">
      <div>
        <div class="page-title" id="section-title" style="margin-bottom:2px"></div>
        <div style="font-size:14px;color:var(--muted)" id="section-sub"></div>
      </div>
      <input class="search-input" id="searchCats" placeholder="🔍 Qidirish..." oninput="renderCategories()">
    </div>
    <div class="section-list" id="catsGrid"></div>
    <div id="addCatBtnWrap" style="display:none">
      <button class="add-flow-btn" onclick="showAddCatForm()">＋ Yangi kategoriya qo'shish</button>
    </div>
    <div id="addCatFormWrap"></div>
  </div>

  <!-- SCREEN: CATEGORY (flows) -->
  <div class="screen" id="screen-cat">
    <div class="progress-bar"><div class="progress-fill" style="width:50%"></div></div>
    <button class="back-btn" onclick="goBack('section')">← Orqaga</button>
    <div class="section-list-header">
      <div>
        <div class="page-title" id="cat-title" style="margin-bottom:2px"></div>
        <div style="font-size:14px;color:var(--muted)" id="cat-sub"></div>
      </div>
      <input class="search-input" id="searchFlows" placeholder="🔍 Qidirish..." oninput="renderFlowList()">
    </div>
    <div class="section-list" id="flowList"></div>
    <div id="addFlowBtnWrap" style="display:none">
      <button class="add-flow-btn" onclick="showFlowForm()">＋ Yangi jarayon qo'shish</button>
    </div>
    <div id="flowFormWrap" style="display:none"></div>
  </div>

  <!-- SCREEN: FLOW (tree) -->
  <div class="screen" id="screen-flow">
    <div class="progress-bar"><div class="progress-fill" style="width:75%"></div></div>
    <button class="back-btn" onclick="goBack('cat')">← Orqaga</button>
    <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:4px">
      <div>
        <div class="page-title" id="flow-title"></div>
        <div class="page-sub" id="flow-sub" style="margin-bottom:0"></div>
      </div>
      <div id="flowHeaderActions" style="display:none;gap:8px;margin-top:4px">
        <button class="btn-sm" onclick="startEditFlowName()">✏ Nomini o'zgartirish</button>
        <button class="btn-sm-danger" onclick="deleteCurrentFlow()">✕ O'chirish</button>
      </div>
    </div>
    <div id="editFlowNameForm" style="display:none;margin-bottom:16px;margin-top:10px"></div>
    <div class="flow-tree" id="flowTree" style="margin-top:20px;overflow-x:auto"></div>
    <div id="rootFormWrap"></div>
  </div>

</div>

<!-- IMAGE MODAL -->
<div class="img-modal" id="imgModal" onclick="closeImgModal()">
  <img id="imgModalSrc" src="" alt="">
</div>

<!-- LOGIN MODAL -->
<div class="modal-overlay" id="loginModal">
  <div class="modal-box">
    <div class="modal-title">Admin kirish</div>
    <div class="modal-sub">Tahrirlash uchun tizimga kiring</div>
    <div style="margin-bottom:10px"><label class="form-label">Login</label><input class="fi" id="loginInput" autocomplete="off"></div>
    <div style="margin-bottom:4px"><label class="form-label">Parol</label><input class="fi" id="passInput" type="password" onkeydown="if(event.key==='Enter')doLogin()"></div>
    <div class="modal-error" id="loginError">Login yoki parol noto'g'ri</div>
    <div class="form-actions" style="margin-top:16px">
      <button class="btn-save" onclick="doLogin()">Kirish</button>
      <button class="btn-cancel" onclick="closeLoginModal()">Bekor</button>
    </div>
  </div>
</div>
<div class="notification" id="notification"></div>

<script>
// ---- AUTH ----
const ADMIN_LOGIN='testlogin',ADMIN_PASS='test26';
let isAdmin=false;
function handleAdminBtn(){isAdmin?doLogout():openLoginModal()}
function openLoginModal(){
  document.getElementById('loginModal').classList.add('open');
  ['loginInput','passInput'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('loginError').classList.remove('show');
  setTimeout(()=>document.getElementById('loginInput').focus(),100);
}
function closeLoginModal(){document.getElementById('loginModal').classList.remove('open')}
function doLogin(){
  const l=document.getElementById('loginInput').value.trim();
  const p=document.getElementById('passInput').value;
  if(l===ADMIN_LOGIN&&p===ADMIN_PASS){
    isAdmin=true;closeLoginModal();
    const btn=document.getElementById('adminBtn');
    btn.classList.add('active');btn.textContent='⚙ Admin (chiqish)';
    document.getElementById('exportBtn').style.display='inline-flex';
    notify('Admin rejimiga kirildingiz ✓');renderCurrent();
  } else {
    document.getElementById('loginError').classList.add('show');
    document.getElementById('passInput').value='';
    document.getElementById('passInput').focus();
  }
}
function doLogout(){
  isAdmin=false;
  const btn=document.getElementById('adminBtn');
  btn.classList.remove('active');btn.textContent='⚙ Admin';
  document.getElementById('exportBtn').style.display='none';
  notify('Chiqildi');renderCurrent();
}
function exportData(){
  const json=JSON.stringify(db,null,2);
  const blob=new Blob([json],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download='biznes-jarayonlar.json';
  document.body.appendChild(a);a.click();
  document.body.removeChild(a);URL.revokeObjectURL(url);
  notify('Ma\'lumotlar saqlandi ✓');
}

// ---- DATA ----
// sections > categories > flows > nodes(tree)
let db = {
  "sections": [
    {
      "id": "sec1",
      "title": "Support",
      "desc": "Mijozlar va hamkorlar bilan ishlash bo'yicha jarayonlar",
      "icon": "📞",
      "categories": [
        {
          "id": "cat1",
          "title": "Mijozlar murojaatlari",
          "desc": "Buyurtma, to'lov, yetkazib berish va boshqa mijoz murojaatlari",
          "icon": "👤",
          "flows": [
            {
              "id": "flow1",
              "title": "Buyurtmani bekor qilish",
              "sub": "Murojaatni qayta ishlash ketma-ketligi",
              "nodes": [
                {
                  "id": "n1779884724663",
                  "name": "Salomlashish",
                  "desc": "",
                  "msg": "Assalomu alaykum ushbu toyhonaga yigilga aziz muxlislar sizlarga man baxt tilyman",
                  "link": "",
                  "img": "",
                  "children": []
                },
                {
                  "id": "n1779884821983",
                  "name": "Mirojat qilinganini vaqtni qaysi toyifada ekanini aniqlash",
                  "desc": "",
                  "msg": "",
                  "link": "",
                  "img": "",
                  "children": [
                    {
                      "id": "n1779884845377",
                      "name": "Yashil vaqt",
                      "desc": "",
                      "msg": "",
                      "link": "",
                      "img": "",
                      "children": []
                    },
                    {
                      "id": "n1779885036389",
                      "name": "Qizil vaqt",
                      "desc": "",
                      "msg": "",
                      "link": "",
                      "img": "",
                      "children": []
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          "id": "cat2",
          "title": "Hamkorlar murojaatlari",
          "desc": "Restoran va yetkazib beruvchilar bilan ishlash",
          "icon": "🤝",
          "flows": []
        }
      ]
    }
  ]
};
// ---- LOCALSTORAGE ----
const DB_KEY="biznes_jarayonlar_db";
function saveDB(){try{localStorage.setItem(DB_KEY,JSON.stringify(db));}catch(e){}}
function loadDB(){try{const saved=localStorage.getItem(DB_KEY);if(saved)db=JSON.parse(saved);}catch(e){}}
loadDB();

// ---- STATE ----
let navHistory=['home'];
let activeSectionId=null, activeCatId=null, activeFlowId=null;

// ---- NAV ----
function goTo(screen){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.getElementById('screen-'+screen).classList.add('active','fade-in');
  navHistory.push(screen);renderCurrent();window.scrollTo(0,0);
}
function goBack(screen){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.getElementById('screen-'+screen).classList.add('active');
  while(navHistory[navHistory.length-1]!==screen) navHistory.pop();
  renderCurrent();window.scrollTo(0,0);
}
function navTo(idx,screen){
  navHistory=navHistory.slice(0,idx+1);
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.getElementById('screen-'+screen).classList.add('active');
  renderCurrent();window.scrollTo(0,0);
}
function renderCurrent(){
  const cur=navHistory[navHistory.length-1];
  if(cur==='home') renderSections();
  else if(cur==='section') renderCategories();
  else if(cur==='cat') renderFlowList();
  else if(cur==='flow') renderFlowTree();
  updateBreadcrumb();
}
function updateBreadcrumb(){
  const sec=db.sections.find(s=>s.id===activeSectionId);
  const cat=sec?.categories.find(c=>c.id===activeCatId);
  const flow=cat?.flows.find(f=>f.id===activeFlowId);
  const names={home:'Bosh sahifa',section:sec?.title||'',cat:cat?.title||'',flow:flow?.title||''};
  let html='';
  navHistory.forEach((h,i)=>{
    if(i<navHistory.length-1) html+=`<span class="breadcrumb-item" onclick="navTo(${i},'${h}')">${names[h]||h}</span><span class="breadcrumb-sep">›</span>`;
    else html+=`<span class="breadcrumb-current">${names[h]||h}</span>`;
  });
  document.getElementById('breadcrumb').innerHTML=html;
}

// ---- SECTIONS (home) ----
function renderSections(){
  const grid=document.getElementById('sectionsGrid');
  let html='';
  db.sections.forEach(sec=>{
    html+=`<div class="nav-card" onclick="openSection('${sec.id}')">
      ${isAdmin?`<div class="nav-card-actions" onclick="event.stopPropagation()">
        <button class="btn-sm" onclick="startEditSection('${sec.id}')">✏</button>
        <button class="btn-sm-danger" onclick="deleteSection('${sec.id}')">✕</button>
      </div>`:''}
      <div class="nav-card-title">${esc(sec.title)}</div>
      <div class="nav-card-desc">${esc(sec.desc||'')}</div>
      <div class="nav-card-arrow">→</div>
    </div>`;
  });
  if(isAdmin){
    html+=`<button class="add-card-btn" onclick="showAddSectionForm()">＋ Bo'lim qo'shish</button>`;
  }
  grid.innerHTML=html;
  document.getElementById('addSectionFormWrap').innerHTML='';
}
function openSection(id){activeSectionId=id;goTo('section')}
function showAddSectionForm(){
  document.getElementById('addSectionFormWrap').innerHTML=`<div class="inline-form fade-in">
    <div class="inline-form-title">＋ Yangi bo'lim</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="nsTitle" placeholder="Bo'lim nomi..."></div>
    <div class="form-row"><label class="form-label">Tavsif</label><input class="fi" id="nsDesc" placeholder="Qisqacha tavsif..."></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveNewSection()">Saqlash</button>
      <button class="btn-cancel" onclick="renderSections()">Bekor</button>
    </div>
  </div>`;
  document.getElementById('nsTitle').focus();
}
function saveNewSection(){
  const title=document.getElementById('nsTitle').value.trim();
  const desc=document.getElementById('nsDesc').value.trim();
  if(!title){notify('Nom kiriting!');return;}
  db.sections.push({id:'sec'+Date.now(),title,desc,categories:[]});
  notify('Saqlandi ✓');saveDB();renderSections();
}
function deleteSection(id){
  if(!confirm('O\'chirasizmi?')) return;
  db.sections=db.sections.filter(s=>s.id!==id);
  notify("O'chirildi ✓");saveDB();renderSections();
}
function startEditSection(id){
  const sec=db.sections.find(s=>s.id===id);if(!sec) return;
  document.getElementById('addSectionFormWrap').innerHTML=`<div class="inline-form fade-in">
    <div class="inline-form-title">✏ Bo'limni tahrirlash</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="esTitle" value="${esc(sec.title)}"></div>
    <div class="form-row"><label class="form-label">Tavsif</label><input class="fi" id="esDesc" value="${esc(sec.desc||'')}"></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveEditSection('${id}')">Saqlash</button>
      <button class="btn-cancel" onclick="renderSections()">Bekor</button>
    </div>
  </div>`;
  document.getElementById('esTitle').focus();
}
function saveEditSection(id){
  const sec=db.sections.find(s=>s.id===id);if(!sec) return;
  sec.title=document.getElementById('esTitle').value.trim()||sec.title;
  sec.desc=document.getElementById('esDesc').value.trim();
  notify('Saqlandi ✓');saveDB();renderSections();
}

// ---- CATEGORIES ----
function renderCategories(){
  const sec=db.sections.find(s=>s.id===activeSectionId);if(!sec) return;
  document.getElementById("section-title").textContent=sec.title;
  document.getElementById("section-sub").textContent=sec.desc||"";
  const q=(document.getElementById("searchCats")?.value||"").trim();
  const filtered=q?sec.categories.filter(c=>fuzzyMatch(c.title,q)):sec.categories;
  const grid=document.getElementById("catsGrid");
  let html="";
  filtered.forEach((cat,i)=>{
    const num=String(i+1).padStart(2,"0");
    html+=`<div class="section-item" draggable="${isAdmin}" 
      ondragstart="dragStart(event,'${cat.id}','cats')"
      ondragover="dragOver(event)"
      ondrop="drop(event,'${cat.id}','cats')"
      ondragend="dragEnd(event)"
      onclick="openCat('${cat.id}')">
`;
    html+=`<div class="section-item-left"><div class="section-num">${num}</div><div><div class="section-name">${cat.title}</div></div></div>`;
    html+=`<div style="display:flex;align-items:center;gap:8px">`;
    if(isAdmin) html+=`<div class="section-actions"><span class="drag-handle" onclick="event.stopPropagation()" style="margin-right:2px">⣿</span><button class="btn-sm" onclick="event.stopPropagation();startEditCat('${cat.id}')">✏</button><button class="btn-sm-danger" onclick="event.stopPropagation();deleteCat('${cat.id}')">✕</button></div>`;
    html+=`<div class="section-chevron">›</div></div></div>`;
  });
  if(!filtered.length) html=`<div class="no-results">${q?"Hech narsa topilmadi 🔍":"Hozircha kategoriyalar yoq"}</div>`;
  grid.innerHTML=html;
  const addBtn=document.getElementById("addCatBtnWrap");
  if(addBtn) addBtn.style.display=isAdmin?"block":"none";
  document.getElementById("addCatFormWrap").innerHTML="";
}
function openCat(id){activeCatId=id;goTo('cat')}
function showAddCatForm(){
  document.getElementById('addCatFormWrap').innerHTML=`<div class="inline-form fade-in">
    <div class="inline-form-title">＋ Yangi kategoriya</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="ncTitle" placeholder="Kategoriya nomi..."></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveNewCat()">Saqlash</button>
      <button class="btn-cancel" onclick="renderCategories()">Bekor</button>
    </div>
  </div>`;
  document.getElementById('ncTitle').focus();
}
function saveNewCat(){
  const sec=db.sections.find(s=>s.id===activeSectionId);if(!sec) return;
  const title=document.getElementById('ncTitle').value.trim();
  if(!title){notify('Nom kiriting!');return;}
  sec.categories.push({id:'cat'+Date.now(),title,desc:'',type:'list',flows:[]});
  notify('Saqlandi ✓');saveDB();renderCategories();
}
function deleteCat(id){
  if(!confirm('O\'chirasizmi?')) return;
  const sec=db.sections.find(s=>s.id===activeSectionId);if(!sec) return;
  sec.categories=sec.categories.filter(c=>c.id!==id);
  notify("O'chirildi ✓");saveDB();renderCategories();
}
function startEditCat(id){
  const sec=db.sections.find(s=>s.id===activeSectionId);
  const cat=sec?.categories.find(c=>c.id===id);if(!cat) return;
  document.getElementById('addCatFormWrap').innerHTML=`<div class="inline-form fade-in">
    <div class="inline-form-title">✏ Kategoriyani tahrirlash</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="ecTitle" value="${esc(cat.title)}"></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveEditCat('${id}')">Saqlash</button>
      <button class="btn-cancel" onclick="renderCategories()">Bekor</button>
    </div>
  </div>`;
  document.getElementById('ecTitle').focus();
}
function saveEditCat(id){
  const sec=db.sections.find(s=>s.id===activeSectionId);
  const cat=sec?.categories.find(c=>c.id===id);if(!cat) return;
  cat.title=document.getElementById('ecTitle').value.trim()||cat.title;
  notify('Saqlandi ✓');saveDB();renderCategories();
}

// ---- FLOWS LIST ----
function getActiveCat(){
  const sec=db.sections.find(s=>s.id===activeSectionId);
  return sec?.categories.find(c=>c.id===activeCatId);
}
function renderFlowList(){
  const cat=getActiveCat();if(!cat) return;
  document.getElementById('cat-title').textContent=cat.title;
  document.getElementById('cat-sub').textContent=cat.desc||'';
  const q=(document.getElementById('searchFlows')?.value||'').trim();
  const flows=cat.flows;
  const filtered=q?flows.filter(f=>fuzzyMatch(f.title,q)):flows;
  let html='';
  filtered.forEach((flow,i)=>{
    const num=String(i+1).padStart(2,'0');
    html+=`<div class="section-item" draggable="${isAdmin}"
      ondragstart="dragStart(event,'${flow.id}','flows')"
      ondragover="dragOver(event)"
      ondrop="drop(event,'${flow.id}','flows')"
      ondragend="dragEnd(event)"
      onclick="openFlow('${flow.id}')">
      <div class="section-item-left">
        <div class="section-num">${num}</div>
        <div><div class="section-name">${esc(flow.title)}</div></div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        ${isAdmin?`<div class="section-actions">
          <span class="drag-handle" onclick="event.stopPropagation()" style="margin-right:2px">⣿</span>
          <button class="btn-sm" onclick="event.stopPropagation();startEditFlowItem('${flow.id}')">✏</button>
          <button class="btn-sm-danger" onclick="event.stopPropagation();deleteFlow('${flow.id}')">✕</button>
        </div>`:''}
        <div class="section-chevron">›</div>
      </div>
    </div>`;
  });
  if(!filtered.length) html=`<div class="no-results">${q?'Hech narsa topilmadi 🔍':'Hozircha jarayonlar yo\'q'}</div>`;
  document.getElementById('flowList').innerHTML=html;
  document.getElementById('addFlowBtnWrap').style.display=isAdmin?'block':'none';
  document.getElementById('flowFormWrap').style.display='none';
}
function openFlow(id){activeFlowId=id;goTo('flow')}
function showFlowForm(){
  document.getElementById('flowFormWrap').style.display='block';
  document.getElementById('addFlowBtnWrap').style.display='none';
  document.getElementById('flowFormWrap').innerHTML=`<div class="inline-form fade-in">
    <div class="inline-form-title">＋ Yangi jarayon</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="nfTitle" placeholder="Jarayon nomi..."></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveNewFlow()">Saqlash</button>
      <button class="btn-cancel" onclick="renderFlowList()">Bekor</button>
    </div>
  </div>`;
  document.getElementById('nfTitle').focus();
}
function saveNewFlow(){
  const cat=getActiveCat();if(!cat) return;
  const title=document.getElementById('nfTitle').value.trim();
  if(!title){notify('Nom kiriting!');return;}
  cat.flows.push({id:'flow'+Date.now(),title,sub:'Murojaatni qayta ishlash ketma-ketligi',nodes:[]});
  notify('Saqlandi ✓');saveDB();renderFlowList();
}
function deleteFlow(id){
  if(!confirm('O\'chirasizmi?')) return;
  const cat=getActiveCat();if(!cat) return;
  cat.flows=cat.flows.filter(f=>f.id!==id);
  notify("O'chirildi ✓");saveDB();renderFlowList();
}
function startEditFlowItem(id){
  const cat=getActiveCat();
  const flow=cat?.flows.find(f=>f.id===id);if(!flow) return;
  document.getElementById('flowFormWrap').style.display='block';
  document.getElementById('addFlowBtnWrap').style.display='none';
  document.getElementById('flowFormWrap').innerHTML=`<div class="inline-form fade-in">
    <div class="inline-form-title">✏ Jarayonni tahrirlash</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="efItemTitle" value="${esc(flow.title)}"></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveEditFlowItem('${id}')">Saqlash</button>
      <button class="btn-cancel" onclick="renderFlowList()">Bekor</button>
    </div>
  </div>`;
}
function saveEditFlowItem(id){
  const cat=getActiveCat();
  const flow=cat?.flows.find(f=>f.id===id);if(!flow) return;
  const title=document.getElementById('efItemTitle').value.trim();
  if(!title) return;
  flow.title=title;notify('Saqlandi ✓');saveDB();renderFlowList();
}

// ---- FLOW TREE ----
function getActiveFlow(){
  const cat=getActiveCat();
  return cat?.flows.find(f=>f.id===activeFlowId);
}
function renderFlowTree(){
  const flow=getActiveFlow();if(!flow) return;
  document.getElementById('flow-title').textContent=flow.title;
  document.getElementById('flow-sub').textContent=flow.sub||'';
  document.getElementById('flowHeaderActions').style.display=isAdmin?'flex':'none';
  document.getElementById('editFlowNameForm').style.display='none';
  document.getElementById('rootFormWrap').innerHTML='';
  const tree=document.getElementById('flowTree');
  let html='<div class="tree-col">';
  flow.nodes.forEach((node,i)=>{
    html+=renderNodeHTML(node,String(i+1).padStart(2,'0'));
  });
  html+='</div>';
  if(isAdmin) html+=`<button class="add-root-btn" onclick="showNodeForm(null,null)">＋ Harakat qo'shish</button>`;
  tree.innerHTML=html;
}
function renderNodeHTML(node,numLabel){
  const hasChildren=node.children&&node.children.length>0;
  const adminBtns=isAdmin?`<div class="node-corner">
    ${node.link?`<button class="corner-btn link-btn" onclick="copyLink('${esc(node.link)}')" title="Linkni nusxa olish">🔗</button>`:''}
    <button class="corner-btn" onclick="showNodeForm('${node.id}',null,true)" title="Tahrirlash">✏</button>
    <button class="corner-btn danger" onclick="deleteNode('${node.id}')" title="O'chirish">✕</button>
  </div>`:(node.link?`<div class="node-corner"><button class="corner-btn link-btn" onclick="copyLink('${esc(node.link)}')" title="Linkni nusxa olish">🔗</button></div>`:'');

  let cardHtml=`<div class="node-card" id="nc-${node.id}">
    <div class="node-num">${numLabel}</div>
    ${adminBtns}
    <div class="node-name">${esc(node.name)}</div>
    ${node.msg?`<div class="node-msg-wrap">
      <div class="node-msg" id="msg-${node.id}">${esc(node.msg)}</div>
      <button class="copy-btn" style="top:6px;right:6px;width:24px;height:24px;font-size:11px" onclick="copyMsg('${node.id}')" title="Nusxa">⧉</button>
    </div>`:''}
    ${node.link?`<div class="node-link">🔗 <a href="${esc(node.link)}" target="_blank" onclick="event.stopPropagation()">${esc(node.link)}</a></div>`:''}
    ${node.img?`<div style="margin-top:8px"><button onclick="event.stopPropagation();openImgModal('${node.id}')" style="border:1px solid var(--border);background:var(--bg);border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;color:var(--muted)">🖼 Rasmni ko'rish</button></div>`:''}
  </div>`;

  let childrenHtml='';
  if(hasChildren||isAdmin){
    childrenHtml+=`<div class="children-connector">
      <div class="v-bar-wrap"><div class="v-bar"></div></div>
      <div class="children-col">`;
    if(node.children){
      node.children.forEach((child,ci)=>{
        childrenHtml+=`<div class="child-row">
          <div class="child-h-line"></div>
          ${renderNodeHTML(child,String(ci+1).padStart(2,'0'))}
        </div>`;
      });
    }
    if(isAdmin){
      childrenHtml+=`<div style="display:flex;align-items:center">
        <div class="child-h-line"></div>
        <button class="add-child-btn" onclick="showNodeForm('${node.id}',null)">＋ Variant qo'shish</button>
      </div>
      <div id="childForm-${node.id}"></div>`;
    }
    childrenHtml+=`</div></div>`;
  }
  return `<div class="node-row" id="nr-${node.id}">
    <div style="display:flex;flex-direction:column">${cardHtml}<div id="editForm-${node.id}"></div></div>
    ${childrenHtml}
  </div>`;
}

function startEditFlowName(){
  const flow=getActiveFlow();if(!flow) return;
  const f=document.getElementById('editFlowNameForm');
  f.style.display='block';
  f.innerHTML=`<div class="inline-form fade-in">
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="efTitle" value="${esc(flow.title)}"></div>
    <div class="form-actions">
      <button class="btn-save" onclick="saveFlowName()">Saqlash</button>
      <button class="btn-cancel" onclick="document.getElementById('editFlowNameForm').style.display='none'">Bekor</button>
    </div>
  </div>`;
  document.getElementById('efTitle').focus();
}
function saveFlowName(){
  const flow=getActiveFlow();if(!flow) return;
  const title=document.getElementById('efTitle').value.trim();if(!title) return;
  flow.title=title;
  document.getElementById('flow-title').textContent=title;
  document.getElementById('editFlowNameForm').style.display='none';
  notify('Saqlandi ✓');saveDB();updateBreadcrumb();
}
function deleteCurrentFlow(){
  if(!confirm('O\'chirasizmi?')) return;
  const cat=getActiveCat();if(!cat) return;
  cat.flows=cat.flows.filter(f=>f.id!==activeFlowId);
  activeFlowId=null;notify("O'chirildi ✓");saveDB();goBack('cat');
}

// ---- NODE FORM ----
function showNodeForm(nodeOrParentId,_,editMode){
  const isEdit=!!editMode;
  const flow=getActiveFlow();
  let node=isEdit?findNode(flow.nodes,nodeOrParentId):null;
  const formId=isEdit?`editForm-${nodeOrParentId}`:(nodeOrParentId&&nodeOrParentId!=='null'?`childForm-${nodeOrParentId}`:'rootFormWrap');
  const target=document.getElementById(formId);if(!target) return;
  target.innerHTML=`<div class="inline-form fade-in" style="width:var(--card-w);margin-top:6px">
    <div class="inline-form-title">${isEdit?'✏ Tahrirlash':'＋ Yangi'}</div>
    <div class="form-row"><label class="form-label">Nomi</label><input class="fi" id="${formId}_name" value="${esc(node?.name||'')}"></div>
    <div class="form-row"><label class="form-label">Xabar matni</label>
      <textarea class="fi" id="${formId}_msg" style="min-height:70px;resize:vertical;font-family:'JetBrains Mono',monospace;font-size:11px">${esc(node?.msg||'')}</textarea></div>
    <div class="form-row"><label class="form-label">Link (ixtiyoriy)</label><input class="fi" id="${formId}_link" value="${esc(node?.link||'')}" placeholder="https://..."></div>
    <div class="form-row"><label class="form-label">Rasm (ixtiyoriy)</label>
      <input type="file" accept="image/*" id="${formId}_img" style="font-size:12px;width:100%">
      ${node?.img?'<div style="font-size:11px;color:var(--muted);margin-top:4px">✓ Rasm biriktirilgan</div>':''}
    </div>
    <div class="form-actions">
      <button class="btn-save" onclick="${isEdit?`saveEditNode('${nodeOrParentId}','${formId}')`:`saveNewNode('${nodeOrParentId}','${formId}')`}">Saqlash</button>
      <button class="btn-cancel" onclick="renderFlowTree()">Bekor</button>
    </div>
  </div>`;
  document.getElementById(formId+'_name').focus();
}
function saveNewNode(parentId,formId){
  const name=document.getElementById(formId+'_name').value.trim();
  const msg=document.getElementById(formId+'_msg').value.trim();
  const link=document.getElementById(formId+'_link').value.trim();
  if(!name){notify('Nom kiriting!');return;}
  const imgFile=document.getElementById(formId+'_img')?.files[0];
  const save=(img)=>{
    const newNode={id:'n'+Date.now(),name,desc:'',msg,link,img:img||'',children:[]};
    const flow=getActiveFlow();
    if(!parentId||parentId==='null') flow.nodes.push(newNode);
    else{const p=findNode(flow.nodes,parentId);if(p) p.children.push(newNode);}
    notify('Saqlandi ✓');saveDB();renderFlowTree();
  };
  if(imgFile){const r=new FileReader();r.onload=e=>save(e.target.result);r.readAsDataURL(imgFile);}
  else save('');
}
function saveEditNode(nodeId,formId){
  const name=document.getElementById(formId+'_name').value.trim();
  const msg=document.getElementById(formId+'_msg').value.trim();
  const link=document.getElementById(formId+'_link').value.trim();
  if(!name){notify('Nom kiriting!');return;}
  const imgFile=document.getElementById(formId+'_img')?.files[0];
  const flow=getActiveFlow();
  const node=findNode(flow.nodes,nodeId);if(!node) return;
  const save=(img)=>{
    node.name=name;node.msg=msg;node.link=link;
    if(img) node.img=img;
    notify('Saqlandi ✓');saveDB();renderFlowTree();
  };
  if(imgFile){const r=new FileReader();r.onload=e=>save(e.target.result);r.readAsDataURL(imgFile);}
  else save('');
}
function deleteNode(nodeId){
  if(!confirm('O\'chirasizmi?')) return;
  const flow=getActiveFlow();
  flow.nodes=removeNode(flow.nodes,nodeId);
  notify("O'chirildi ✓");saveDB();renderFlowTree();
}
function findNode(nodes,id){for(const n of nodes){if(n.id===id)return n;const f=findNode(n.children||[],id);if(f)return f;}return null;}
function removeNode(nodes,id){return nodes.filter(n=>n.id!==id).map(n=>({...n,children:removeNode(n.children||[],id)}));}

// ---- DRAG & DROP ----
let dragId=null,dragType=null;
function dragStart(e,id,type){dragId=id;dragType=type;e.currentTarget.classList.add('dragging');}
function dragOver(e){e.preventDefault();e.currentTarget.classList.add('drag-over');}
function dragEnd(e){e.currentTarget.classList.remove('dragging');document.querySelectorAll('.drag-over').forEach(el=>el.classList.remove('drag-over'));}
function drop(e,targetId,type){
  e.preventDefault();
  document.querySelectorAll('.drag-over').forEach(el=>el.classList.remove('drag-over'));
  if(!dragId||dragId===targetId) return;
  const sec=db.sections.find(s=>s.id===activeSectionId);
  if(type==='flows'){
    const cat=getActiveCat();if(!cat) return;
    const arr=cat.flows;
    const fi=arr.findIndex(x=>x.id===dragId),ti=arr.findIndex(x=>x.id===targetId);
    if(fi<0||ti<0) return;
    const [item]=arr.splice(fi,1);arr.splice(ti,0,item);
    saveDB();renderFlowList();
  } else if(type==='cats'){
    const arr=sec.categories.filter(c=>c.type!=='card');
    const fi=arr.findIndex(x=>x.id===dragId),ti=arr.findIndex(x=>x.id===targetId);
    const allArr=sec.categories;
    const afi=allArr.findIndex(x=>x.id===dragId),ati=allArr.findIndex(x=>x.id===targetId);
    if(afi<0||ati<0) return;
    const [item]=allArr.splice(afi,1);allArr.splice(ati,0,item);
    saveDB();renderCategories();
  }
  dragId=null;
}

// ---- IMAGE MODAL ----
function openImgModal(nodeId){
  const flow=getActiveFlow();
  const node=findNode(flow.nodes,nodeId);if(!node||!node.img) return;
  document.getElementById('imgModalSrc').src=node.img;
  document.getElementById('imgModal').classList.add('open');
}
function closeImgModal(){
  document.getElementById('imgModal').classList.remove('open');
  document.getElementById('imgModalSrc').src='';
}

// ---- UTILS ----
function copyMsg(id){
  const el=document.getElementById('msg-'+id);if(!el) return;
  navigator.clipboard.writeText(el.textContent).then(()=>{
    const btn=el.parentElement.querySelector('.copy-btn');
    btn.classList.add('copied');btn.textContent='✓';
    notify('Nusxa olindi ✓');
    setTimeout(()=>{btn.classList.remove('copied');btn.textContent='⧉'},2000);
  });
}
function copyLink(link){navigator.clipboard.writeText(link).then(()=>notify('Link nusxa olindi ✓'))}
function fuzzyMatch(str,q){
  str=str.toLowerCase();q=q.toLowerCase();
  if(str.includes(q))return true;
  let si=0,qi=0;while(si<str.length&&qi<q.length){if(str[si]===q[qi])qi++;si++;}
  if(qi===q.length)return true;
  if(q.length>=3){for(const w of str.split(' ')){if(lev(w.slice(0,q.length+2),q)<=2)return true;}}
  return false;
}
function lev(a,b){
  const m=a.length,n=b.length,d=Array.from({length:m+1},(_,i)=>Array.from({length:n+1},(_,j)=>i===0?j:j===0?i:0));
  for(let i=1;i<=m;i++)for(let j=1;j<=n;j++)d[i][j]=a[i-1]===b[j-1]?d[i-1][j-1]:1+Math.min(d[i-1][j],d[i][j-1],d[i-1][j-1]);
  return d[m][n];
}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function notify(msg){const n=document.getElementById('notification');n.textContent=msg;n.classList.add('show');setTimeout(()=>n.classList.remove('show'),2000)}
document.getElementById('loginModal').addEventListener('click',function(e){if(e.target===this)closeLoginModal()});

// INIT
renderSections();
updateBreadcrumb();
</script>
</body>
</html>
