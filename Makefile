# Atajos de desarrollo. En Windows usa los comandos directamente o WSL/Git Bash.
.PHONY: install install-eval lint fmt typecheck test check lock

install:        ## Instala dependencias (base: webhook + ingesta + admin)
	python -m pip install --upgrade pip
	pip install -r requirements.txt

install-eval:   ## Instala dependencias de evaluación (RAGAS/DeepEval, entorno aparte)
	python -m pip install --upgrade pip
	pip install -r requirements-eval.txt

lint:           ## Linter (ruff)
	ruff check .

fmt:            ## Autoformatea y corrige lo autofixeable
	ruff check --fix .

typecheck:      ## Verificación de tipos (mypy, gradual)
	mypy

test:           ## Tests
	pytest -q

check: lint typecheck test  ## Calidad completa (lint + tipos + tests)

lock:           ## Genera los locks pinneados y reproducibles (requiere pip-tools)
	python -m pip install --upgrade pip-tools
	pip-compile requirements.txt --output-file requirements.lock --quiet
	pip-compile requirements-eval.txt --output-file requirements-eval.lock --quiet
	@echo "Locks generados: requirements.lock (Dockerfiles) y requirements-eval.lock (evaluación local)."
