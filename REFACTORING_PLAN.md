# 考題知識整理系統 - 重構計畫備忘錄

## 願景

將應用程式從一個單純的資料整理工具，升級為一個以「知識點」為核心的個人化學習系統。建立一個強大的「知識資料網」，讓使用者可以圍繞核心概念進行主題式複習，實現高效學習。

## 核心思路

建立一個以 **知識點 (Knowledge Point)** 為中心的資料庫結構，打造一個一定會考高分上榜的 **知識圖譜 (Knowledge Graph)**。

---
基礎功能已經大致上完成
1.現在需要在webUI上做出**知識圖譜 (Knowledge Graph)**
           <!-- 上傳檔案 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">📁</div>
                        <h3 class="card-title">分析題目</h3>
                        <p class="card-text text-muted">自動解析考題與知識點，不限於檔案，也包含文字與url</p>
                        <a href="/upload" class="btn btn-primary">開始上傳</a>
                    </div>
                </div>
            </div>
            
            <!-- 題庫瀏覽 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">📚</div>
                        <h3 class="card-title">題庫瀏覽</h3>
                        <p class="card-text text-muted">瀏覽已處理的題目，支援 Markdown 渲染和程式碼高亮</p>
                        <a href="/questions" class="btn btn-primary">瀏覽題庫</a>
                    </div>
                </div>
            </div>
            
            <!-- 知識庫 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">🧠</div>
                        <h3 class="card-title">知識庫</h3>
                        <p class="card-text text-muted">查看知識點分類與統計，了解學習進度</p>
                        <a href="/knowledge" class="btn btn-primary">查看知識庫</a>
                    </div>
                </div>
            </div>
            
            <!-- 原始文件 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">📜</div>
                        <h3 class="card-title">原始文件</h3>
                        <p class="card-text text-muted">查看所有已上傳的原始文件內容，對照學習更有效</p>
                        <a href="/documents" class="btn btn-success">檢視文件</a>
                    </div>
                </div>
            </div>
        </div>
要在這下面新增，這個區塊與按鈕，當然要對齊上面四個區塊 並且抱持一致風格

2.並且刪除有關桌面版的程式碼，減少冗餘的代碼與檔案
3.需要增加可以對接到SQL伺服器的功能，因為輕量型的DB或許會吃不消
<<<<<<< HEAD
4.研究不限於上面這些功能以外，可以讓學習更加完善的功能
=======
4.研究不限於上面這些功能以外，可以讓學習更加完善的功能
>>>>>>> f7688b802d1377238b33c71cfc2121e83e162c82
