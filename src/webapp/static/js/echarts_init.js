/**
 * ECharts 初始化和工具函數
 */

// 檢查 ECharts 是否可用
document.addEventListener('DOMContentLoaded', function() {
    if (typeof echarts === 'undefined') {
        console.error('ECharts 庫未載入，可能會影響心智圖顯示功能');
    } else {
        console.log('ECharts 庫已成功載入');
    }
});

/**
 * 渲染心智圖的函數
 * @param {string} containerId - 圖表容器的 ID
 * @param {Object} data - 心智圖數據
 * @param {Object} options - 自定義配置
 */
function renderMindmap(containerId, data, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`找不到ID為 ${containerId} 的容器元素`);
        return;
    }
    
    if (!data) {
        console.error('心智圖數據為空');
        container.innerHTML = '<div class="alert alert-warning">無法渲染心智圖：數據為空</div>';
        return;
    }
    
    try {
        const chart = echarts.init(container);
        
        // 默認配置
        const defaultOptions = {
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
                    symbolSize: 10,
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
        
        // 合併自定義配置
        const finalOptions = Object.assign({}, defaultOptions, options);
        
        // 設置圖表選項
        chart.setOption(finalOptions);
        
        // 讓圖表隨視窗大小變動
        window.addEventListener('resize', () => chart.resize());
        
        console.log('心智圖渲染成功');
        return chart;
    } catch (error) {
        console.error('心智圖渲染失敗:', error);
        container.innerHTML = `<div class="alert alert-danger">
            <i class="fas fa-exclamation-triangle me-2"></i>
            心智圖渲染失敗：${error.message}
        </div>`;
        return null;
    }
}

// 暴露給全局使用
window.renderMindmap = renderMindmap;
