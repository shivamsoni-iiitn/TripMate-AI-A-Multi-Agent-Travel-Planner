let currentThreadId = localStorage.getItem("travel_thread_id") || null;
let latestAnswerMarkdown = "";

function setPrompt(text) {
    document.getElementById("userInput").value = text;
}

function setLoading(isLoading) {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");

    sendBtn.disabled = isLoading;

    if (isLoading) {
        btnText.classList.add("hidden");
        btnLoader.classList.remove("hidden");
    } else {
        btnText.classList.remove("hidden");
        btnLoader.classList.add("hidden");
    }
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");

    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    const errorBox = document.getElementById("errorBox");

    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

function renderMarkdownToHtml(markdown) {
    if (typeof window !== "undefined" && typeof window.marked !== "undefined" && typeof window.marked.parse === "function") {
        return window.marked.parse(markdown);
    }

    const lines = String(markdown || "").split(/\r?\n/);
    const htmlParts = [];
    let listItems = [];

    const flushList = () => {
        if (listItems.length) {
            htmlParts.push(`<ul>${listItems.map((item) => `<li>${item}</li>`).join("")}</ul>`);
            listItems = [];
        }
    };

    const formatInline = (value) => {
        return value
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");
    };

    lines.forEach((line) => {
        const trimmed = line.trim();

        if (!trimmed) {
            flushList();
            return;
        }

        if (/^#{1,3}\s+/.test(trimmed)) {
            flushList();
            const level = Math.min(trimmed.match(/^#+/)[0].length, 3);
            const text = formatInline(trimmed.replace(/^#{1,3}\s+/, ""));
            htmlParts.push(`<h${level}>${text}</h${level}>`);
        } else if (/^[-*]\s+/.test(trimmed)) {
            listItems.push(formatInline(trimmed.replace(/^[-*]\s+/, "")));
        } else {
            flushList();
            htmlParts.push(`<p>${formatInline(trimmed)}</p>`);
        }
    });

    flushList();
    return htmlParts.join("");
}

function showResult(answer, threadId) {
    latestAnswerMarkdown = answer;

    const resultSection = document.getElementById("resultSection");
    const resultBox = document.getElementById("resultBox");
    const threadInfo = document.getElementById("threadInfo");

    resultBox.innerHTML = renderMarkdownToHtml(answer);

    threadInfo.textContent = `Thread ID: ${threadId}`;

    resultSection.classList.remove("hidden");

    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

async function sendMessage() {
    hideError();

    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (!message) {
        showError("Please enter your travel request first.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        currentThreadId = data.thread_id;
        localStorage.setItem("travel_thread_id", currentThreadId);

        showResult(data.answer, data.thread_id);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

function copyResult() {
    const resultBox = document.getElementById("resultBox");
    const text = resultBox.innerText;

    if (!text) {
        return;
    }

    navigator.clipboard.writeText(text)
        .then(() => {
            const copyBtn = document.querySelector(".copy-btn");
            const oldText = copyBtn.textContent;

            copyBtn.textContent = "Copied!";

            setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 1400);
        })
        .catch(() => {
            showError("Could not copy result.");
        });
}

function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");

    if (!latestAnswerMarkdown || !pdfContent) {
        showError("No travel plan available to download.");
        return;
    }

    const downloadBtn = document.querySelector(".download-btn");
    const oldText = downloadBtn.textContent;

    downloadBtn.textContent = "Preparing PDF...";
    downloadBtn.disabled = true;

    const options = {
        margin: 0.5,
        filename: "ai-travel-plan.pdf",
        image: {
            type: "jpeg",
            quality: 0.98
        },
        html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff"
        },
        jsPDF: {
            unit: "in",
            format: "a4",
            orientation: "portrait"
        },
        pagebreak: {
            mode: ["avoid-all", "css", "legacy"]
        }
    };

    html2pdf()
        .set(options)
        .from(pdfContent)
        .save()
        .then(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
        })
        .catch(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
            showError("Could not download PDF.");
        });
}

document.addEventListener("keydown", function(event) {
    if (event.ctrlKey && event.key === "Enter") {
        sendMessage();
    }
});