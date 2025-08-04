// 這個修復腳本用來檢查並修復前端JavaScript事件綁定問題
// 當加號按鈕被點擊時，應該顯示組織選擇器模態框，並正確處理按鈕事件

console.log("正在檢查和修復AI整理筆記功能...");

// 檢查是否在note_detail.html頁面
if (document.getElementById('note-content-tabs')) {
    console.log("找到筆記詳情頁面，開始檢查加號按鈕...");
    
    // 檢查加號按鈕是否存在
    const addButton = document.getElementById('add-organization-tab');
    if (addButton) {
        console.log("找到加號按鈕，確認點擊事件...");
        
        // 確保showOrganizationSelector函數存在
        if (typeof showOrganizationSelector === 'function') {
            console.log("showOrganizationSelector函數存在");
            
            // 重新綁定點擊事件，以確保它會被觸發
            addButton.onclick = null; // 清除可能存在的舊事件
            addButton.addEventListener('click', function(event) {
                console.log("加號按鈕被點擊");
                showOrganizationSelector();
                event.preventDefault();
            });
            
            console.log("已重新綁定加號按鈕事件");
        } else {
            console.error("錯誤: showOrganizationSelector函數不存在");
        }
    } else {
        console.error("錯誤: 找不到加號按鈕 (id: add-organization-tab)");
    }
    
    // 為document添加全局事件監聽器，確保模態框中的按鈕被正確處理
    document.addEventListener('click', function(event) {
        const target = event.target.closest('.organization-btn');
        if (target) {
            console.log("組織按鈕被點擊", target.dataset);
            const type = target.getAttribute('data-type');
            const name = target.getAttribute('data-name');
            const icon = target.getAttribute('data-icon');
            
            // 檢查selectOrganizationType函數是否存在
            if (typeof selectOrganizationType === 'function') {
                console.log(`調用selectOrganizationType(${type}, ${name}, ${icon})`);
                selectOrganizationType(type, name, icon);
            } else {
                console.error("錯誤: selectOrganizationType函數不存在");
            }
        }
    });
    
    console.log("已添加全局事件監聽器");
    
    // 檢查loadingModal是否被正確初始化
    setTimeout(() => {
        if (typeof loadingModal === 'undefined' || loadingModal === null) {
            console.warn("警告: loadingModal未初始化，嘗試重新初始化...");
            try {
                const loadingModalElement = document.getElementById('loadingModal');
                if (loadingModalElement) {
                    window.loadingModal = new bootstrap.Modal(loadingModalElement);
                    console.log("loadingModal已重新初始化");
                }
            } catch (e) {
                console.error("重新初始化loadingModal失敗:", e);
            }
        } else {
            console.log("loadingModal已正確初始化");
        }
    }, 500);
    
    alert("AI整理筆記功能修復完成！請重新嘗試點擊加號按鈕。");
} else {
    console.error("錯誤: 當前不在筆記詳情頁面");
    alert("此修復腳本需要在筆記詳情頁面上運行。");
}
