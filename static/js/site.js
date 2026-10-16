(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector(".theme-toggle");
  const savedTheme = localStorage.getItem("monerkotha-theme");
  if (savedTheme === "dark") root.dataset.theme = "dark";
  themeButton?.addEventListener("click", () => {
    const isDark = root.dataset.theme !== "dark";
    root.dataset.theme = isDark ? "dark" : "light";
    localStorage.setItem("monerkotha-theme", isDark ? "dark" : "light");
  });

  const content = document.querySelector("#id_content");
  const counter = document.querySelector("[data-character-count]");
  const bengaliDigits = (value) => String(value).replace(/\d/g, (digit) => "০১২৩৪৫৬৭৮৯"[Number(digit)]);
  const updateCount = () => {
    if (content && counter) counter.textContent = `${bengaliDigits(content.value.length)} / ৩০০০`;
  };
  content?.addEventListener("input", updateCount);
  updateCount();

  document.querySelectorAll("[data-dialog-open]").forEach((button) => {
    button.addEventListener("click", () => document.getElementById(button.dataset.dialogOpen)?.showModal());
  });
  document.querySelectorAll("[data-dialog-close]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  document.querySelectorAll("[data-reaction-form] button").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      const form = button.closest("form");
      const data = new FormData(form);
      data.set("kind", button.value);
      const feedback = document.querySelector("[data-reaction-feedback]");
      if (feedback) feedback.textContent = "আপনার প্রতিক্রিয়া পাঠানো হচ্ছে…";
      button.disabled = true;
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: data,
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error("প্রতিক্রিয়া পাঠানো যায়নি। আবার চেষ্টা করুন।");
        const count = await response.text();
        const countLabel = form.querySelector("button[value='heart'] span");
        if (countLabel) countLabel.textContent = bengaliDigits(count);
        button.setAttribute("aria-pressed", "true");
        if (feedback) feedback.textContent = "আপনার প্রতিক্রিয়া যোগ হয়েছে। ধন্যবাদ!";
      } catch (error) {
        button.disabled = false;
        if (feedback) feedback.textContent = error.message;
      }
    });
  });

  document.querySelectorAll("form[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit']");
      if (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.dataset.originalText = button.textContent;
        button.textContent = "জমা হচ্ছে…";
      }
    });
  });
})();
