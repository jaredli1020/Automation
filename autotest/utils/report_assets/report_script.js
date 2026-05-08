// 报告脚本 - 简易版本，业务项目可覆盖以添加图表/交互等功能
(function(){
    var results = JSON.parse(document.getElementById('d-r').textContent || '[]');
    var screenshots = JSON.parse(document.getElementById('d-s').textContent || '{}');
    var moduleNames = JSON.parse(document.getElementById('d-m').textContent || '{}');

    var currentMod = '';
    var currentFilter = 'all';
    var currentSearch = '';
    var currentPage = 1;
    var pageSize = 50;

    window.navTo = function(el){
        document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active')});
        el.classList.add('active');
        currentMod = el.dataset.mod || '';
        document.getElementById('page-overview').classList.remove('active');
        document.getElementById('page-list').classList.remove('active');
        if(!currentMod){
            document.getElementById('page-overview').classList.add('active');
        } else {
            document.getElementById('page-list').classList.add('active');
            renderList();
        }
    };

    window.applyFilter = function(f, btn){
        currentFilter = f;
        currentPage = 1;
        document.querySelectorAll('.filter-btn').forEach(function(b){b.classList.remove('active')});
        btn.classList.add('active');
        renderList();
    };

    window.applySearch = function(v){
        currentSearch = (v||'').toLowerCase();
        currentPage = 1;
        renderList();
    };

    window.closeScreenshot = function(){
        document.getElementById('overlay').classList.remove('show');
    };

    function filteredResults(){
        return results.filter(function(r){
            if(currentMod && currentMod !== '__all__' && r.module !== currentMod) return false;
            if(currentFilter !== 'all' && r.outcome !== currentFilter) return false;
            if(currentSearch){
                var text = (r.name+' '+(r.api_path||'')).toLowerCase();
                if(text.indexOf(currentSearch) < 0) return false;
            }
            return true;
        });
    }

    function renderList(){
        var list = filteredResults();
        var start = (currentPage-1)*pageSize;
        var slice = list.slice(start, start+pageSize);
        var container = document.getElementById('testContainer');
        container.innerHTML = slice.map(function(r){
            var cls = 'status-'+r.outcome;
            return '<div class="test-item"><span class="tname">'+escape(r.name)+
                   (r.api_path?' <span style="color:#999;font-size:12px">'+escape(r.api_path)+'</span>':'')+
                   '</span><span class="tstatus '+cls+'">'+r.outcome+'</span></div>';
        }).join('');

        var total = list.length;
        var pages = Math.max(1, Math.ceil(total/pageSize));
        var pag = document.getElementById('pagination');
        var html = '';
        for(var i=1;i<=pages;i++){
            html += '<button class="'+(i===currentPage?'active':'')+'" onclick="goPage('+i+')">'+i+'</button>';
        }
        pag.innerHTML = html;
    }

    window.goPage = function(p){ currentPage = p; renderList(); };

    function escape(s){
        return String(s||'').replace(/[&<>"']/g, function(c){
            return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
        });
    }
})();
