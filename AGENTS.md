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
