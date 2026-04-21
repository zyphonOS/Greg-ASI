(function () {
    const form = document.getElementById("blog-generate-form");
    const promptNode = document.getElementById("blog-generate-prompt");
    const resultNode = document.getElementById("blog-generate-result");

    if (!form || !promptNode || !resultNode) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const prompt = promptNode.value.trim();
        if (!prompt) {
            resultNode.textContent = "A prompt is required.";
            return;
        }
        resultNode.textContent = "Generating pending draft…";
        try {
            const response = await fetch("/api/blog/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt }),
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Unable to generate article.");
            }
            resultNode.textContent = `Draft saved as pending review: ${payload.post.title}`;
            promptNode.value = "";
        } catch (error) {
            resultNode.textContent = error.message || "Blog generation failed.";
        }
    });
})();
