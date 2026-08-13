.PHONY: install run dev clean freeze

install:
	pip install -r requirements.txt

run:
	streamlit run app.py

dev:
	streamlit run app.py --server.runOnSave true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true

freeze:
	pip freeze > requirements.txt
