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

  const submissionFeedback = document.querySelector("[data-submit-feedback]");
  const clearSubmissionErrors = (form) => {
    form.querySelectorAll("[data-field-errors]").forEach((container) => {
      container.replaceChildren();
      container.hidden = true;
    });
  };
  const showSubmissionErrors = (form, fields) => {
    let shown = false;
    Object.entries(fields || {}).forEach(([name, errors]) => {
      const container = form.querySelector(`[data-field-errors="${name}"]`);
      if (!container) return;
      const messages = Array.isArray(errors) ? errors : [errors];
      messages.forEach((error) => {
        const message = typeof error === "string" ? error : error.message;
        if (!message) return;
        const item = document.createElement("div");
        item.textContent = message;
        container.append(item);
        shown = true;
      });
      container.hidden = container.childElementCount === 0;
    });
    return shown;
  };

  document.querySelectorAll("form[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      const button = form.querySelector("button[type='submit']");
      if (!form.dataset.apiUrl) {
        if (button) {
          button.disabled = true;
          button.setAttribute("aria-busy", "true");
          button.dataset.originalText = button.textContent;
          button.textContent = "জমা হচ্ছে…";
        }
        return;
      }

      event.preventDefault();
      const originalButtonNodes = button
        ? Array.from(button.childNodes, (node) => node.cloneNode(true))
        : [];
      if (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.textContent = "জমা হচ্ছে…";
      }

      if (submissionFeedback) {
        submissionFeedback.hidden = true;
        submissionFeedback.textContent = "";
        submissionFeedback.classList.remove("message-error");
        submissionFeedback.classList.add("message-success");
      }
      clearSubmissionErrors(form);
      const showFeedback = (message, isError = false) => {
        if (!submissionFeedback) return;
        submissionFeedback.textContent = message;
        submissionFeedback.classList.toggle("message-error", isError);
        submissionFeedback.classList.toggle("message-success", !isError);
        submissionFeedback.hidden = false;
      };

      try {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        data.consent_given = form.elements.namedItem("consent_given").checked;
        const response = await fetch(form.dataset.apiUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": formData.get("csrfmiddlewaretoken"),
          },
          body: JSON.stringify(data),
          credentials: "same-origin",
        });
        const payload = await response.json();
        if (!response.ok) {
          const error = payload.error || {};
          const hasFieldErrors = showSubmissionErrors(form, error.fields);
          const message = response.status === 429
            ? "এই ঘণ্টায় গল্প জমা দেওয়ার সীমা পূর্ণ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।"
            : hasFieldErrors
              ? "গল্পটি জমা দেওয়া যায়নি। চিহ্নিত তথ্যগুলো ঠিক করে আবার চেষ্টা করুন।"
              : "গল্পটি জমা দেওয়া যায়নি। কিছুক্ষণ পর আবার চেষ্টা করুন।";
          showFeedback(message, true);
          return;
        }

        form.reset();
        updateCount();
        showFeedback("আপনার গল্পটি পেয়েছি। পর্যালোচনার পর উপযুক্ত হলে প্রকাশ করা হবে।");
      } catch {
        showFeedback("সার্ভারের সঙ্গে সংযোগ করা যায়নি। ইন্টারনেট পরীক্ষা করে আবার চেষ্টা করুন।", true);
      } finally {
        if (button) {
          button.disabled = false;
          button.removeAttribute("aria-busy");
          button.replaceChildren(...originalButtonNodes);
        }
      }
    });
  });
})();
