// static/js/components/search_variantes.js
// ==============================
// SMART SEARCH COMPONENT PRO
// Shopify / POS Ready
// ==============================

export function initVariantSearch({
    inputId,
    hiddenId,
    dropdownId,
    url,
    minChars = 2,
    onSelect = null
}) {

    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const box = document.getElementById(dropdownId);

    let timeout = null;
    let selectedIndex = -1;
    let items = [];

    // =========================
    // RESET
    // =========================
    const reset = () => {
        hidden.value = "";
        selectedIndex = -1;
        items = [];
    };

    input.addEventListener("input", function () {

        reset();

        clearTimeout(timeout);

        const q = this.value.trim();

        if (q.length < minChars) {
            box.innerHTML = "";
            return;
        }

        timeout = setTimeout(() => {

            fetch(`${url}?q=${encodeURIComponent(q)}`)
                .then(res => res.json())
                .then(data => {

                    items = data;
                    box.innerHTML = "";

                    data.forEach((item, index) => {

                        const el = document.createElement("div");

                        el.className = "list-group-item list-group-item-action";
                        el.dataset.index = index;

                        el.innerHTML = `
                            <div>
                                <strong>${item.text}</strong>
                            </div>
                            <small class="text-muted">
                                SKU: ${item.sku || ""}
                            </small>
                        `;

                        el.onclick = () => selectItem(index);

                        box.appendChild(el);
                    });

                });

        }, 200);
    });

    // =========================
    // SELECT ITEM
    // =========================
    const selectItem = (index) => {

        const item = items[index];
        if (!item) return;

        input.value = item.text;
        hidden.value = item.id;
        box.innerHTML = "";

        selectedIndex = -1;

        if (onSelect) {
            onSelect(item);
        }
    };

    // =========================
    // KEYBOARD NAVIGATION (POS READY)
    // =========================
    input.addEventListener("keydown", function (e) {

        const listItems = box.querySelectorAll(".list-group-item");

        if (!listItems.length) return;

        // ↓
        if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % listItems.length;
            highlight(listItems);
        }

        // ↑
        if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + listItems.length) % listItems.length;
            highlight(listItems);
        }

        // ENTER (scanner + POS friendly)
        if (e.key === "Enter") {
            e.preventDefault();

            if (selectedIndex >= 0) {
                selectItem(selectedIndex);
            } else if (items.length === 1) {
                selectItem(0);
            }
        }
    });

    // =========================
    // HIGHLIGHT UI
    // =========================
    const highlight = (listItems) => {

        listItems.forEach((el, i) => {
            el.classList.remove("active");
            if (i === selectedIndex) {
                el.classList.add("active");
            }
        });
    };

    // =========================
    // CLICK OUTSIDE CLOSE
    // =========================
    document.addEventListener("click", (e) => {
        if (!box.contains(e.target) && e.target !== input) {
            box.innerHTML = "";
        }
    });
}