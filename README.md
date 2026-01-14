# FakeN: TruthSeeker 🛡️

A sophisticated **Compound AI** system designed to verify social media misinformation (especially Indian "WhatsApp Forwards") using a hybrid approach of Machine Learning, Retrieval-Augmented Generation (RAG), and Large Language Models.

## 🚀 Key Features

*   **Triple-Layer Verification**:
    1.  **Stylistic Analysis**: Detects manipulative writing styles (emojis, urgency, emotional hyperbole) using Scikit-Learn.
    2.  **RAG Engine**: Grounds the AI in a verified Knowledge Base of 50+ facts to prevent hallucinations.
    3.  **Gemini 2.5 Flash**: Orchestrates the final reasoning, providing human-like explanations.
*   **Skeptical Logic**: Successfully identifies when a topic is real but the specific claim is exaggerated.
*   **Modern UI**: Sleek, glassmorphic chat interface with real-time risk scoring and color-coded verdicts.

## 🛠️ Technology Stack

*   **Frontend**: React + Vite, Vanilla CSS
*   **Backend**: FastAPI (Python)
*   **AI/ML**: Google Gemini 2.5 Flash, Scikit-Learn (TF-IDF + Logistic Regression)
*   **Documentation**: Includes auto-generated Project Reports (Word) and Presentations (PPTX).

## 📥 Installation & Setup

### 1. Backend Setup
1. Navigate to the `backend` folder: `cd backend`
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: `.\venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file and add your Gemini API Key:
   ```text
   GEMINI_API_KEY=your_key_here
   ```
6. Start the server: `python main.py`

### 2. Frontend Setup
1. Navigate to the `frontend` folder: `cd frontend`
2. Install dependencies: `npm install`
3. Start the dev server: `npm run dev`

## 📖 Project Documentation
The project includes detailed reports and presentations in the `backend/` folder:
- `FakeN_Project_Report.docx`
- `FakeN_Project_Presentation.pptx`

---
*Developed as a prototype for advanced AI fact-checking.*
