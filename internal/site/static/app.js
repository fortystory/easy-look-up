// 快速查找 —— 前端交互
//
// 只做三件事：主题切换、搜索过滤、复制代码。
// 全部是原生 JavaScript，不依赖任何框架和 CDN。

(function () {
	"use strict";

	/* ---------- 主题切换 ---------- */

	var toggle = document.getElementById("theme-toggle");

	function currentTheme() {
		var attr = document.documentElement.getAttribute("data-theme");
		if (attr === "light" || attr === "dark") {
			return attr;
		}
		return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
	}

	function paintToggle() {
		if (!toggle) {
			return;
		}
		toggle.textContent = currentTheme() === "dark" ? "☀️" : "🌙";
	}

	if (toggle) {
		paintToggle();
		toggle.addEventListener("click", function () {
			var next = currentTheme() === "dark" ? "light" : "dark";
			document.documentElement.setAttribute("data-theme", next);
			try {
				localStorage.setItem("theme", next);
			} catch (e) {
				// 隐私模式下 localStorage 不可用，忽略即可
			}
			paintToggle();
		});
	}

	/* ---------- 搜索过滤 ---------- */

	var input = document.getElementById("search");

	if (input) {
		var groups = Array.prototype.slice.call(document.querySelectorAll(".group"));

		function applyFilter() {
			var q = input.value.trim().toLowerCase();
			groups.forEach(function (group) {
				var visible = 0;
				Array.prototype.forEach.call(group.querySelectorAll(".entry"), function (entry) {
					var haystack = (entry.getAttribute("data-search") || "").toLowerCase();
					var hit = q === "" || haystack.indexOf(q) !== -1;
					entry.hidden = !hit;
					if (hit) {
						visible++;
					}
				});
				group.hidden = visible === 0;
			});
		}

		input.addEventListener("input", applyFilter);
	}

	/* ---------- 复制代码 ---------- */

	function fallbackCopy(text, done) {
		var area = document.createElement("textarea");
		area.value = text;
		area.setAttribute("readonly", "");
		area.style.position = "fixed";
		area.style.top = "-1000px";
		document.body.appendChild(area);
		area.select();
		try {
			document.execCommand("copy");
			done();
		} catch (e) {
			// 复制失败就静默处理，按钮不会显示「已复制」
		}
		document.body.removeChild(area);
	}

	Array.prototype.forEach.call(document.querySelectorAll(".copy-btn"), function (btn) {
		btn.addEventListener("click", function () {
			var text = btn.getAttribute("data-code") || "";
			var done = function () {
				btn.textContent = "已复制";
				btn.classList.add("done");
				setTimeout(function () {
					btn.textContent = "复制";
					btn.classList.remove("done");
				}, 1500);
			};
			if (navigator.clipboard && navigator.clipboard.writeText) {
				navigator.clipboard.writeText(text).then(done, function () {
					fallbackCopy(text, done);
				});
			} else {
				fallbackCopy(text, done);
			}
		});
	});
})();
