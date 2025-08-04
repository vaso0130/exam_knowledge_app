重大工程：題庫與筆記系統整合計畫
目標：
在題庫的「問題列表」和「問題詳情」頁面加入「加入筆記」功能，允許使用者為特定題目創建個人化筆記，並可選擇手動編輯或由 AI 自動生成。

Phase 1: 前端介面修改 (UI)
修改 questions.html (問題列表頁)

位置: f:\exam_knowledge_app\src\webapp\templates\questions.html
任務: 在每一題的迴圈中，於「查看詳情」按鈕旁，新增一個「✍️ 加入筆記」按鈕或連結。
連結指向: 這個按鈕將指向一個新的路由，例如：url_for('notes.create_note_from_question', question_id=question.id)。
修改 question_detail.html (問題詳情頁)

位置: f:\exam_knowledge_app\src\webapp\templates\question_detail.html
任務: 在頁面上的顯眼位置（例如問題卡片的頂部或底部）新增一個更明確的「為此題建立筆記」按鈕。
連結指向: 同上，指向 url_for('notes.create_note_from_question', question_id=question.id)。
Phase 2: 後端路由與邏輯 (Backend)
在 notes_blueprint.py 中建立新路由

位置: f:\exam_knowledge_app\src\webapp\notes_blueprint.py
任務: 建立一個新的 Flask 路由來處理來自前端的請求。
路由定義:
def create_note_from_question(question_id):
    # ... 路由的邏輯將在這裡實現 ...
實現 GET 請求邏輯 (載入筆記編輯器)

目的: 當使用者點擊「加入筆記」時，顯示一個預先填充好來源資訊的筆記編輯頁面。
步驟:
使用 question_id 從主資料庫 (DatabaseManager) 中查詢對應的題目和答案。
渲染 note_edit.html 模板。
將查詢到的 question 物件傳遞給模板，以便在頁面上顯示「來源題目」。
筆記標題可以預設為：「筆記：[題目文字前30個字]...」。
筆記內容預設為空，讓使用者可以開始編輯。
實現 POST 請求邏輯 (AI 生成筆記)

目的: 當使用者在編輯頁面點擊「AI 自動生成筆記」按鈕時，觸發後端生成筆記。
步驟:
同樣的路由 create_note_from_question 將處理這個 POST 請求。
從請求中獲取 question_id。
再次查詢題目資料。
呼叫 NoteManager 中現有的 create_note_from_questions 方法。這個方法非常適合這個場景，我們只需要將單一題目資料包裝成一個列表傳入即可。
# 在路由函式中
question_data = main_db.get_question_by_id(question_id)
note_id = note_manager.create_note_from_questions(
    user_id=current_user.id,
    questions_data=[{'question_text': question_data['text'], 'answer_text': question_data['answer']}]
)
筆記成功建立後，將使用者重導向到新建立的筆記詳情頁面：redirect(url_for('notes.note_detail', note_id=note_id))。
Phase 3: 筆記編輯器增強 (UI/UX)
修改 note_edit.html (筆記編輯頁)
位置: f:\exam_knowledge_app\src\webapp\templates\notes\note_edit.html
任務:
新增一個區塊，使用 {% if source_question %} 判斷式來顯示傳入的題目資訊。
在這個區塊中，美觀地展示 source_question.text (題目) 和 source_question.answer (答案)，作為使用者撰寫筆記時的參考。
在標準的「儲存筆記」按鈕旁，新增一個「🚀 AI 自動生成筆記」按鈕。這個按鈕會觸發到 create_note_from_question 路由的 POST 請求。
使用者手動填寫內容並點擊「儲存筆記」的流程將維持不變，但後端儲存邏輯需要確保能正確處理從題目建立的筆記。
實施順序
我將依照以下順序開始實作：

從後端開始：先在 notes_blueprint.py 建立好路由和基本的 GET 邏輯。
修改前端模板：接著修改 questions.html 和 question_detail.html，將按鈕加上去，確保它們能正確連結到新路由。
增強筆記編輯器：修改 note_edit.html 以顯示來源題目和 AI 生成按鈕。
完成後端 POST 邏輯：實現 AI 生成筆記的功能並完成重導向。
測試：進行完整的功能測試。

Phase 4: 筆記編輯與檢視頁面增強 (UI/UX)

修改 note_edit.html (筆記編輯頁)：
新增一個可收合的 (collapsible) 區塊。
預設收合，標題為「顯示/隱藏來源題目」。
區塊內顯示傳入的 source_question 的題目和答案。
提供「AI 自動生成筆記」按鈕。
修改 note_detail.html (筆記檢視頁)：
使用 {% if note.source_question %} 判斷。
如果為真，則顯示一個返回按鈕/連結，文字為「返回原始題目」，連結指向 url_for('main.question_detail', question_id=note.source_question.id)。
同樣新增一個可收合的區塊，預設收合，用於顯示來源題目和答案。