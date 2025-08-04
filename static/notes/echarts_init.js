// ECharts 相關功能初始化和工具函數

// 初始化頁面上所有ECharts圖表
function initializeAllCharts() {
    console.log("初始化所有圖表...");
    // 這個函數可以在頁面載入或切換分頁時呼叫
    // 目前我們不需要額外的初始化，因為各個圖表在創建時會自動初始化
}

// 當頁面載入完成或切換標籤時，初始化圖表
document.addEventListener('DOMContentLoaded', function() {
    // 監聽標籤頁切換事件
    document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(function(tab) {
        tab.addEventListener('shown.bs.tab', function(e) {
            console.log("標籤頁切換:", e.target.getAttribute('data-bs-target'));
            setTimeout(initializeAllCharts, 100); // 延遲初始化，確保DOM已渲染
        });
    });
    
    // 監聽模態視窗打開事件
    document.querySelectorAll('.modal').forEach(function(modal) {
        modal.addEventListener('shown.bs.modal', function() {
            console.log("模態視窗開啟");
            setTimeout(initializeAllCharts, 100);
        });
    });
});

// 渲染心智圖函數
function renderMindmap(container, data) {
    if (!container || !data) return false;
    
    try {
        const myChart = echarts.init(container);
        
        const option = {
            tooltip: {
                trigger: 'item',
                triggerOn: 'mousemove'
            },
            series: [
                {
                    type: 'tree',
                    data: [data], // ECharts 需要一個陣列
                    top: '5%',
                    left: '10%',
                    bottom: '5%',
                    right: '20%',
                    symbolSize: 10, // 節點大小
                    label: {
                        position: 'left',
                        verticalAlign: 'middle',
                        align: 'right',
                        fontSize: 14
                    },
                    leaves: {
                        label: {
                            position: 'right',
                            verticalAlign: 'middle',
                            align: 'left'
                        }
                    },
                    emphasis: {
                        focus: 'descendant'
                    },
                    expandAndCollapse: true,
                    animationDuration: 550,
                    animationDurationUpdate: 750
                }
            ]
        };
        
        myChart.setOption(option);
        // 讓圖表隨視窗大小變動
        window.addEventListener('resize', () => myChart.resize());
        return true;
    } catch (e) {
        console.error("ECharts 初始化失敗:", e);
        container.innerHTML = `<div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle me-2"></i>
            圖表渲染失敗，請檢查資料格式或重新整理頁面。
            <br><small class="text-muted">${e.message}</small>
        </div>`;
        return false;
    }
}
