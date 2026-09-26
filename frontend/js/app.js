const API_URL = "http://127.0.0.1:8000";

const askBtn = document.getElementById("askBtn");
const query = document.getElementById("query");
const jurisdiction = document.getElementById("jurisdiction");
const answer = document.getElementById("answer");
const answerText = document.getElementById("answerText");
const sources = document.getElementById("sources");

askBtn.addEventListener("click", async () => {
  const text = query.value.trim();
  if (!text) {
    alert("Please enter a question.");
    return;
  }

  askBtn.disabled = true;
  askBtn.textContent = "Thinking...";
  answer.hidden = false;
  answerText.textContent = "Processing your question...";
  sources.innerHTML = "";

  try {
    const response = await fetch(API_URL + "/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: text,
        jurisdiction: jurisdiction.value,
        language: document.getElementById("language").value
      })
    });

    if (!response.ok) throw new Error("API request failed");
    const data = await response.json();

    answerText.textContent = data.answer;
    (data.sources || []).forEach(source => {
      const li = document.createElement("li");
      li.textContent = source;
      sources.appendChild(li);
    });
  } catch (error) {
    answerText.textContent = "Could not connect to the backend. Start FastAPI with: uvicorn main:app --reload";
  } finally {
    askBtn.disabled = false;
    askBtn.textContent = "Ask IP-SAKTI";
  }
});
