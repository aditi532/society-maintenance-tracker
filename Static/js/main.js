document.querySelectorAll("input, textarea, select").forEach((field) => {
  field.addEventListener("focus", () => field.classList.add("focused"));
  field.addEventListener("blur", () => field.classList.remove("focused"));
});

const photoInput = document.querySelector("#photo");
if (photoInput) {
  photoInput.addEventListener("change", () => {
    const label = document.querySelector(".upload-label strong");
    label.textContent = photoInput.files[0]?.name || "Choose file";
  });
}
