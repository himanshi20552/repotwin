# RepoTwin

### Repository Intelligence and Code Understanding

RepoTwin is a repository analysis tool that builds a structured view of a software codebase and uses it to answer questions about the repository.

Instead of treating a repository as a collection of text files, RepoTwin combines source-code analysis, dependency relationships, repository history, retrieval, and local LLMs to build a more useful picture of how the codebase is organized and how its components relate to each other.

The goal is to make large or unfamiliar repositories easier to understand, explore, and reason about.

---

## What RepoTwin Does

RepoTwin takes a Git repository and analyzes it from several perspectives:

- Repository structure and source files
- Python AST information
- Classes, functions, and methods
- Dependencies and relationships between components
- Call-graph information
- Potential change impact
- Risk and test impact
- Git history
- Semantic code retrieval
- LLM-based repository questions

The resulting information is combined into an analysis context that can be used by an LLM to answer repository-specific questions.

---

## Why RepoTwin?

Understanding an unfamiliar codebase usually requires jumping between files, searching for definitions, tracing dependencies, and looking through Git history.

A simple LLM prompt does not have access to all of this information and can easily miss relationships between files.

RepoTwin takes a different approach:

```text
Repository
    |
    +-- Source Code
    |      |
    |      +-- AST Analysis
    |      +-- Classes / Functions
    |      +-- Dependencies
    |
    +-- Repository Graph
    |      |
    |      +-- Calls
    |      +-- Relationships
    |      +-- Impact Analysis
    |
    +-- Git History
    |
    +-- Code Retrieval
           |
           +-- Chunking
           +-- Embeddings
           +-- Vector Search
                    |
                    v
                  Ollama
                    |
                    v
             Repository-aware Answer

The LLM is given structured repository evidence and retrieved code instead of relying only on the question itself.

Core Features
Repository Analysis

Repositories can be imported and analyzed from their Git URL.

RepoTwin builds information about:

Files
Classes
Functions
Methods
Imports
Relationships
Repository structure
Code and Dependency Graph

RepoTwin builds a graph representation of the repository.

The graph can be used to reason about relationships between components, including:

Function calls
Class relationships
Module dependencies
Call paths
Connected components

This provides a structural view of the codebase in addition to the raw source code.

Impact Analysis

Given a repository component, RepoTwin can trace related components and estimate what parts of the codebase may be affected by a change.

This is useful for questions such as:

What parts of the repository depend on this function?

or:

What could be affected if this component changes?

Risk and Test Impact Analysis

Repository analysis is combined with dependency and test information to identify potentially affected areas and related tests.

This helps connect code changes with their possible consequences elsewhere in the repository.

Git History

RepoTwin also uses repository history as an additional source of information.

Git history can provide context about:

Previous changes
Commits
Frequently modified areas
Historical changes to relevant files

This adds a time dimension to repository understanding rather than looking only at the current source tree.

Repository-Aware RAG

RepoTwin includes a retrieval pipeline for finding relevant parts of a codebase.

The pipeline is roughly:

Repository
    |
    v
Code Chunking
    |
    v
Embeddings
    |
    v
Vector Store
    |
    v
Semantic Retrieval
    |
    v
Relevant Code Context
    |
    v
LLM

For a user question, RepoTwin retrieves code that is semantically related to the question and combines it with the other repository evidence before generating an answer.

This helps the model focus on the actual implementation rather than relying only on its pretrained knowledge.

LLM Integration

RepoTwin currently uses Ollama to run local language models.

The LLM layer is separated from the repository analysis components, so the repository analysis pipeline does not depend directly on a particular model.

Models can be selected through configuration.

Example models used during development and evaluation include:

qwen2.5-coder:1.5b
starcoder2:3b
opencoder:1.5b

The LLM receives repository-specific context assembled by RepoTwin and produces the final explanation or response.

Evaluation and Benchmarking

RepoTwin includes an evaluation pipeline for measuring how well code-focused LLMs understand a repository.

The benchmark contains questions covering:

Explanation
Code Retrieval
Dependency Understanding
Bug Analysis
Code Generation
Refactoring
RAG based Question

The evaluation pipeline supports comparing multiple models using the same questions and repository.

It can also compare RAG and non-RAG configurations.

Metrics collected include:

Correctness
Retrieval precision and recall
Hallucination indicators
Response latency
Prompt and output token counts
Tokens per second
CPU usage
Memory usage
GPU memory usage when available
Python syntax validation for generated code

Evaluation results are saved incrementally so longer experiments can be resumed if interrupted.

Architecture

RepoTwin is organized as a modular FastAPI application.

backend/
├── app/
│   ├── analysis/
│   │   ├── evidence.py
│   │   └── test_impact.py
│   │
│   ├── analyzers/
│   │   └── python_analyzer.py
│   │
│   ├── graph/
│   │   ├── call_graph.py
│   │   ├── impact.py
│   │   ├── repository_graph.py
│   │   ├── repository_twin.py
│   │   ├── risk.py
│   │   ├── typed_graph.py
│   │   └── unified_graph.py
│   │
│   ├── history/
│   │   └── git_history.py
│   │
│   ├── retrieval/
│   │   └── evidence_retriever.py
│   │
│   ├── services/
│   │   ├── chunking_service.py
│   │   ├── embedding_service.py
│   │   ├── llm_service.py
│   │   ├── rag_service.py
│   │   ├── repository_analyzer.py
│   │   ├── repository_service.py
│   │   └── vector_store.py
│   │
│   └── validation/
│       └── evidence_validator.py
│
├── evaluation/
│   ├── dataset.json
│   ├── ground_truth.json
│   ├── evaluator.py
│   ├── scoring.py
│   ├── metrics.py
│   ├── analyze_results.py
│   ├── resource_monitor.py
│   ├── code_validator.py
│   └── setup_repo.py
│
├── requirements.txt
└── Dockerfile

frontend/
└── src/
    └── App.jsx

The backend is built as one FastAPI application with separate logical services rather than a collection of independently deployed microservices.

Main Components
Component	Responsibility
Repository Service	Cloning and managing repositories
Python Analyzer	Extracting source-code information
Graph Engine	Building repository and call relationships
Evidence Analysis	Combining repository analysis results
Impact Analysis	Finding potentially affected components
Risk Analysis	Identifying potentially risky areas
Git History	Working with repository history
Chunking Service	Splitting source code into retrieval units
Embedding Service	Converting code/text into vectors
Vector Store	Storing and searching embeddings
RAG Service	Retrieving and assembling relevant context
LLM Service	Building prompts and communicating with Ollama
Validation	Checking generated claims against repository evidence
Tech Stack
Backend
Python
FastAPI
Pydantic
GitPython
NetworkX
AI / Retrieval
Ollama
Sentence Transformers
Vector-based semantic retrieval
RAG
Frontend
React
Vite
JavaScript
Bootstrap
Infrastructure
Docker
Docker Compose
Git
Running with Docker
Prerequisites

Make sure the following are installed:

Docker
Docker Compose
Ollama
Git

Pull the models you want to use:

ollama pull qwen2.5-coder:1.5b
ollama pull starcoder2:3b
ollama pull opencoder:1.5b
Start the application

Clone the repository:

git clone https://github.com/himanshi20552/repotwin.git
cd repotwin

Create your environment file:

cp .env.example .env

Then start the services:

docker compose up -d --build
Configuration

RepoTwin uses environment variables for configuration.

Important settings include:

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=opencoder:1.5b
EMBEDDING_MODEL=all-MiniLM-L6-v2

When running the backend inside Docker while Ollama runs on the host, Docker uses:

http://host.docker.internal:11434

The Docker Compose configuration handles this without requiring the host machine's IP address to be hardcoded into the application.

Evaluation

The evaluation tools are located under:

backend/evaluation/

Run the evaluator from the backend environment:

python -m evaluation.evaluator

After the evaluation finishes, analyze the collected results:

python -m evaluation.analyze_results

The evaluation pipeline produces aggregated results that can be used to compare models across the different repository-understanding categories.

For longer runs, the evaluator saves intermediate results so that an interrupted experiment can continue from the existing checkpoint.

Example Workflow

A typical RepoTwin workflow looks like this:

1. Provide a Git repository
          |
          v
2. Clone / load repository
          |
          v
3. Analyze source code
          |
          v
4. Build repository graph
          |
          v
5. Analyze dependencies and impact
          |
          v
6. Read relevant Git history
          |
          v
7. Build searchable code representation
          |
          v
8. Retrieve relevant code
          |
          v
9. Assemble repository evidence
          |
          v
10. Send context to local LLM
          |
          v
11. Validate and return repository-aware response
Example Questions

RepoTwin is designed for questions such as:

What does APIRouter do in this repository?

Where is solve_dependencies implemented?

Which components depend on this function?

What happens when this API route is registered?

Which tests are related to this component?

What parts of the codebase might be affected by changing this function?

Can you explain how these modules interact?

The focus is on questions that require understanding the repository rather than general programming knowledge.

Current Scope

RepoTwin currently focuses on repository analysis, graph-based code understanding, retrieval, and LLM-assisted reasoning.

The system is primarily designed around Python repositories, with the architecture allowing additional language support to be added later.

Limitations

RepoTwin is still an evolving project.

Current limitations include:

Analysis quality depends on the structure and language of the repository.
LLM responses can still contain incorrect interpretations.
Local model performance depends heavily on available CPU, memory, and GPU resources.
Repository-wide analysis can become expensive for very large codebases.
Retrieval quality depends on the quality of code chunking and embeddings.
Some analyses are currently more mature for Python repositories than for other languages.
Future Improvements

Potential future work includes:

Better multi-language repository parsing
More precise dependency and call-graph analysis
Improved repository retrieval
Better handling of very large repositories
More robust code-generation validation
Deeper Git-history analysis
Repository-wide refactoring assistance
Automated documentation generation
Additional LLM providers and models
Improved visualization of repository relationships
Project Status

RepoTwin is an actively developed project focused on combining traditional software-engineering analysis with modern LLM and retrieval techniques.

The project explores how structured program analysis, repository graphs, semantic retrieval, and language models can work together to improve codebase understanding.

License

This project is currently intended for educational and research purposes.
