(function () {
  const toolbarOptions = [
    ["bold", "italic", "underline"],
    [{ list: "ordered" }, { list: "bullet" }],
    ["link", "blockquote", "clean"],
  ];

  function setupEditor(textarea) {
    const wrapper = document.createElement("div");
    wrapper.className = "quill-wrapper";

    const editorEl = document.createElement("div");
    editorEl.className = "quill-editor";
    wrapper.appendChild(editorEl);

    const parent = textarea.parentNode;
    parent.insertBefore(wrapper, textarea);
    textarea.setAttribute("hidden", "hidden");
    wrapper.appendChild(textarea);

    const quill = new Quill(editorEl, {
      theme: "snow",
      placeholder: textarea.getAttribute("placeholder") || "",
      modules: {
        toolbar: toolbarOptions,
      },
    });

    const initial = textarea.value ? textarea.value.trim() : "";
    if (initial) {
      quill.clipboard.dangerouslyPasteHTML(initial);
    }

    const sync = () => {
      textarea.value = quill.root.innerHTML.trim();
    };

    quill.on("text-change", sync);

    const form = textarea.closest("form");
    if (form) {
      form.addEventListener("submit", sync);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const textareas = document.querySelectorAll("textarea[data-richtext]");
    if (!textareas.length) return;
    if (typeof Quill === "undefined") {
      console.error("Quill no está disponible");
      return;
    }
    textareas.forEach(setupEditor);
  });
})();
