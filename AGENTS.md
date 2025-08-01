# 安全防護

1.新增認證頁面，需要輸入帳號密碼才能使用網站
附註：先不需要做出個人帳號管理的功能，只需要在前端，先做出一個登入認證後，就能使用網站的認證頁面。

2.新增額外程式，脫離主程式，用來創造帳號密碼，這個創建帳號密碼的功能，只有本地端能夠使用，所以會是完全脫離主程式，並且佔用不同port，讓管理者只能在本地端新增帳號

3.完成後更新README.md，說明新增連接DB、改用wsgi、與新增帳號認證

# 以下改版計畫先忽視
# Please disregard the following revision plan for now.

# Development Guide for AI Agents

This repository powers an AI-driven exam knowledge system. Follow the guidelines below when extending the project.

## Goal
Implement the knowledge graph visualization referenced in `REFACTORING_PLAN.md`. The `/knowledge-graph` route currently displays a placeholder. We need an interactive graph to show how knowledge points relate.

## Tasks
1. **Backend API**
   - Provide an endpoint (e.g., `/api/knowledge-graph`) returning JSON with `nodes` and `edges` representing knowledge points and their relationships.
   - Use existing database tables (`knowledge_points`, `question_knowledge_points` and related tables) to assemble the data. Add helper queries in `DatabaseManager` if required.

2. **Frontend Visualization**
   - Update `knowledge_graph.html` to render the graph using **D3.js** or **Cytoscape.js**.
   - Fetch the API data via AJAX and allow interactions such as zooming, panning and clicking nodes to reveal related questions or details.
   - Keep styling consistent with the current Bootstrap layout.

3. **Documentation**
   - Document setup steps for the knowledge graph feature in `README.md`.
   - Add any new dependencies to `requirements.txt`.

## General Guidelines
- Keep changes focused on the knowledge graph unless fixing small bugs encountered during development.
- Write modular Python functions with docstrings.
- Manual testing can be done by running `python web_app.py` and navigating to `/knowledge-graph`.
- Refer to `REFACTORING_PLAN.md` for broader context.
