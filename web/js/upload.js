/** 图片收集：拖拽、选择、粘贴三种入口统一成一个文件队列。 */

export const MAX_COUNT = 5;
export const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["image/png", "image/jpeg", "image/webp"];

export function rejectReason(file) {
  if (!ACCEPTED.includes(file.type)) return `${file.name || "该文件"} 不是 PNG / JPG / WEBP`;
  if (file.size > MAX_BYTES) return `${file.name || "该文件"} 超过 10MB`;
  return null;
}

/**
 * @param {object} options
 * @param {HTMLElement} options.dropzone
 * @param {HTMLInputElement} options.input
 * @param {HTMLElement} options.thumbs
 * @param {(files: File[], rejected: string[]) => void} options.onChange
 */
export function createUploader({ dropzone, input, thumbs, onChange }) {
  /** @type {{file: File, url: string}[]} */
  let items = [];
  /** @type {string[]} */
  let lastRejected = [];

  const emit = () => onChange(items.map((item) => item.file), lastRejected);

  function render() {
    thumbs.textContent = "";
    items.forEach((item, index) => {
      const cell = document.createElement("div");
      cell.className = "thumb";

      const img = document.createElement("img");
      img.src = item.url;
      img.alt = `第 ${index + 1} 张`;
      img.loading = "lazy";
      cell.append(img);

      const idx = document.createElement("span");
      idx.className = "idx";
      idx.textContent = String(index + 1);
      cell.append(idx);

      const del = document.createElement("button");
      del.type = "button";
      del.className = "del";
      del.textContent = "×";
      del.title = "移除这张";
      del.addEventListener("click", (event) => {
        event.stopPropagation();
        URL.revokeObjectURL(item.url);
        items.splice(index, 1);
        render();
        emit();
      });
      cell.append(del);

      thumbs.append(cell);
    });
  }

  function add(fileList) {
    const rejected = [];
    for (const file of fileList) {
      if (items.length >= MAX_COUNT) {
        rejected.push(`最多 ${MAX_COUNT} 张`);
        break;
      }
      const reason = rejectReason(file);
      if (reason) {
        rejected.push(reason);
        continue;
      }
      items.push({ file, url: URL.createObjectURL(file) });
    }
    lastRejected = rejected;
    render();
    emit();
    return rejected;
  }

  function clear() {
    items.forEach((item) => URL.revokeObjectURL(item.url));
    items = [];
    lastRejected = [];
    render();
    emit();
  }

  dropzone.addEventListener("click", () => input.click());
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });

  input.addEventListener("change", () => {
    add(Array.from(input.files || []));
    input.value = "";
  });

  ["dragenter", "dragover"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      if (type === "dragleave" && dropzone.contains(event.relatedTarget)) return;
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) add(files);
  });

  // 支持直接粘贴截图
  document.addEventListener("paste", (event) => {
    const files = Array.from(event.clipboardData?.files || []).filter((file) => file.type.startsWith("image/"));
    if (!files.length) return;
    event.preventDefault();
    add(files);
  });

  return {
    add,
    clear,
    get files() {
      return items.map((item) => item.file);
    },
    get count() {
      return items.length;
    },
  };
}
