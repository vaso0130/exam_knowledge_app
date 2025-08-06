# 📊 資料庫擴展與重複問題預防建議

## 🔍 現況分析
- **Questions**: 38 題，**Knowledge Points**: 187 個
- **平均關聯密度**: 每題 4.03 個知識點
- **目前重複狀況**: ✅ 無重複關聯

## 🚨 關鍵風險點

### 1. **並行操作風險** 🔴 HIGH
**風險場景**: 多用戶同時生成模擬題
- 當題目數量 > 1000 時，並行重複風險顯著增加
- 預估企業級應用 (5000 題) 將有 20,150 個關聯關係

### 2. **知識點命名衝突** 🟡 MEDIUM  
**風險場景**: AI 生成相似但略有差異的知識點名稱
- 例如："資料庫設計" vs "資料庫設計原則"
- 可能導致知識點碎片化

### 3. **筆記系統擴展** 🟡 MEDIUM
**風險場景**: 筆記功能大量使用時
- 目前筆記關聯為 0，但未來可能快速增長
- 需要在功能擴展前建立防護機制

### 4. **學習資料架構缺失** 🔴 HIGH
**問題**: Documents 沒有直接與 Knowledge Points 關聯
- 只能透過 Questions 間接關聯
- 限制了知識點的來源追蹤和管理

## 💡 解決方案建議

### **立即實施** (高優先級)

#### 1. 建立 Document-Knowledge 直接關聯
```sql
CREATE TABLE document_knowledge_links (
    document_id VARCHAR(36) NOT NULL,
    knowledge_point_id INT NOT NULL,
    relevance_score FLOAT DEFAULT 0.8,
    extraction_method VARCHAR(50), -- 'manual', 'ai_generated', 'question_derived'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, knowledge_point_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id) ON DELETE CASCADE
);
```

#### 2. 強化知識點去重機制
```python
def add_or_get_knowledge_point_safe(self, name: str, subject: str, description: str = "") -> int:
    """
    安全的知識點創建，包含智慧去重
    """
    with self._session_scope() as session:
        # 1. 精確匹配
        kp = session.query(KnowledgePoint).filter_by(name=name.strip()).first()
        if kp:
            return kp.id
            
        # 2. 相似度檢查（防止AI生成的相似知識點）
        similar_kps = session.query(KnowledgePoint).filter(
            KnowledgePoint.subject == subject,
            KnowledgePoint.name.like(f"%{name.strip()[:10]}%")
        ).all()
        
        for similar_kp in similar_kps:
            similarity = self._calculate_similarity(name, similar_kp.name)
            if similarity > 0.85:  # 85% 相似度閾值
                print(f"發現相似知識點: '{name}' -> '{similar_kp.name}' (相似度: {similarity:.2f})")
                return similar_kp.id
        
        # 3. 創建新知識點
        new_kp = KnowledgePoint(name=name.strip(), subject=subject, description=description)
        session.add(new_kp)
        session.flush()
        return new_kp.id
```

#### 3. 加強筆記系統防護
```python
def link_note_to_knowledge_point_safe(self, user_id: int, note_id: str, knowledge_point_id: int, relevance_score: float = 0.8) -> bool:
    """安全的筆記-知識點關聯，防止重複"""
    try:
        with self._session_scope() as session:
            # 驗證用戶權限和資源存在性
            note_exists = session.query(UserNote.id).filter_by(id=note_id, user_id=user_id).first()
            kp_exists = session.query(KnowledgePoint.id).filter_by(id=knowledge_point_id).first()

            if note_exists and kp_exists:
                # 使用 merge 避免重複，但加上額外檢查
                existing = session.query(NoteKnowledgeLink).filter_by(
                    note_id=note_id, 
                    knowledge_point_id=knowledge_point_id
                ).first()
                
                if existing:
                    print(f"筆記 {note_id} 與知識點 {knowledge_point_id} 的關聯已存在")
                    return True
                
                link = NoteKnowledgeLink(
                    note_id=note_id, 
                    knowledge_point_id=knowledge_point_id,
                    relevance_score=relevance_score
                )
                session.add(link)
                session.commit()
                return True
            return False
            
    except Exception as e:
        print(f"建立筆記-知識點關聯時發生錯誤: {e}")
        return False
```

### **中期改進** (中優先級)

#### 1. 資料庫監控機制
```python
def monitor_duplicate_risks(self) -> Dict[str, Any]:
    """監控重複關聯風險"""
    with self._session_scope() as session:
        stats = {}
        
        # 檢查各關聯表的重複情況
        for table_name, pk_cols in [
            ('question_knowledge_links', ['question_id', 'knowledge_point_id']),
            ('note_knowledge_links', ['note_id', 'knowledge_point_id']),
            ('note_category_links', ['note_id', 'category_id']),
            ('document_knowledge_links', ['document_id', 'knowledge_point_id'])  # 新增
        ]:
            try:
                pk_str = ', '.join(pk_cols)
                duplicate_count = session.execute(text(f'''
                    SELECT COUNT(*) FROM (
                        SELECT {pk_str}, COUNT(*) as cnt 
                        FROM {table_name} 
                        GROUP BY {pk_str} 
                        HAVING cnt > 1
                    ) as duplicates
                ''')).scalar()
                stats[table_name] = duplicate_count
            except:
                stats[table_name] = 'TABLE_NOT_EXISTS'
        
        return stats
```

#### 2. 知識點相似度計算
```python
def _calculate_similarity(self, text1: str, text2: str) -> float:
    """計算兩個知識點名稱的相似度"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
```

### **長期規劃** (低優先級)

#### 1. 分散式鎖機制
考慮在高並行環境下使用 Redis 分散式鎖

#### 2. 知識點層次結構
建立知識點的層次關係，避免過度碎片化

#### 3. 自動化清理機制
定期檢查和清理孤立的關聯關係

## 📈 擴展性準備

### 資料量級別對應策略
- **< 1,000 題**: 目前機制足夠
- **1,000 - 5,000 題**: 需要實施中期改進
- **> 5,000 題**: 需要完整的長期規劃解決方案

### 效能監控指標
1. **關聯創建成功率**: > 99%
2. **重複關聯檢出率**: < 0.1%
3. **知識點去重率**: 監控相似知識點的合併情況
4. **資料庫鎖等待時間**: < 100ms

---

## ✅ 總結

目前系統在小規模使用下表現良好，但需要在功能擴展前實施預防措施。**重點關注 Documents 與 Knowledge Points 的直接關聯機制建立**，這將為未來的知識管理奠定基礎。
