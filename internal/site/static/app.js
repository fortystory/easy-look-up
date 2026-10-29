// 快速查找 —— 前端交互
//
// 做四件事：主题切换、搜索过滤、复制代码、侧边栏高亮当前分组。
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

	/* ---------- 侧边栏高亮当前分组 ---------- */

	var navLinks = Array.prototype.slice.call(document.querySelectorAll(".group-nav a"));
	var sections = navLinks
		.map(function (a) {
			return document.getElementById(a.getAttribute("href").slice(1));
		})
		.filter(Boolean);
	var ticking = false;

	// 滚动到哪个分组，就把侧边栏里对应的那一项标成当前
	function updateActive() {
		ticking = false;
		if (!sections.length) {
			return;
		}

		var offset = 120;
		var current = null;
		sections.forEach(function (s) {
			if (s.hidden) {
				// 被搜索过滤掉的分组不算
				return;
			}
			if (s.getBoundingClientRect().top <= offset) {
				current = s;
			}
		});
		if (!current) {
			return;
		}

		navLinks.forEach(function (a) {
			a.classList.toggle("active", a.getAttribute("href") === "#" + current.id);
		});
	}

	if (sections.length) {
		window.addEventListener(
			"scroll",
			function () {
				if (!ticking) {
					ticking = true;
					window.requestAnimationFrame(updateActive);
				}
			},
			{ passive: true }
		);
		updateActive();
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
			// 过滤后要重新算当前分组
			updateActive();
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
