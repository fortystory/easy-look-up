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
	var pinned = null;
	var pinTimer = null;

	// 吸顶的元素会盖住内容：顶栏，窄屏还有分组导航。
	// 宽屏时分组导航是独立的左栏，不遮正文，不算进来。
	//
	// 关键：锚点跳转的落点和高亮的判定线必须用同一个高度，
	// 否则点中一个分组，判定时算出来的是上一个。
	function stickyOffset() {
		var offset = 0;
		var main = document.querySelector("main");
		var mainRect = main ? main.getBoundingClientRect() : null;

		var els = document.querySelectorAll(".site-header, .group-nav");
		for (var i = 0; i < els.length; i++) {
			var el = els[i];
			var cs = window.getComputedStyle(el);
			if (cs.position !== "sticky") {
				continue;
			}
			if (mainRect) {
				// 和正文横向不重叠 = 在旁边，不挡路
				var r = el.getBoundingClientRect();
				if (!(r.left < mainRect.right && mainRect.left < r.right)) {
					continue;
				}
			}
			var bottom = (parseFloat(cs.top) || 0) + el.getBoundingClientRect().height;
			if (bottom > offset) {
				offset = bottom;
			}
		}

		document.documentElement.style.setProperty("--sticky-offset", offset + "px");
		return offset;
	}

	function setActive(id) {
		navLinks.forEach(function (a) {
			a.classList.toggle("active", a.getAttribute("href") === "#" + id);
		});
	}

	function isAtBottom() {
		var doc = document.documentElement;
		return window.innerHeight + window.scrollY >= doc.scrollHeight - 2;
	}

	// 滚动到哪个分组，就把侧边栏里对应的那一项标成当前
	function updateActive() {
		ticking = false;
		if (!sections.length) {
			return;
		}

		var line = stickyOffset();

		// 刚点了导航链接、正在平滑滚动：先跟着点的那一个走，滚到位再交还给滚动判定
		if (pinned) {
			var target = document.getElementById(pinned);
			if (target && Math.abs(target.getBoundingClientRect().top - line) > 4) {
				return;
			}
			pinned = null;
		}

		var current = null;
		var lastVisible = null;
		for (var i = 0; i < sections.length; i++) {
			var s = sections[i];
			if (s.hidden) {
				// 被搜索过滤掉的分组不算
				continue;
			}
			if (s.getBoundingClientRect().top <= line + 2) {
				lastVisible = s;
			}
		}
		current = lastVisible;

		// 滚到底了：最后一个分组可能还没越过判定线（页面不够长，滚不动了）
		if (!current || isAtBottom()) {
			for (var j = sections.length - 1; j >= 0; j--) {
				if (!sections[j].hidden) {
					current = sections[j];
					break;
				}
			}
		}

		if (current) {
			setActive(current.id);
		}
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
		window.addEventListener("resize", function () {
			stickyOffset();
			updateActive();
		});

		// 点导航：立刻高亮，并记住这个选择直到滚动到位
		navLinks.forEach(function (a) {
			a.addEventListener("click", function () {
				pinned = a.getAttribute("href").slice(1);
				setActive(pinned);
				window.clearTimeout(pinTimer);
				pinTimer = window.setTimeout(function () {
					pinned = null;
					updateActive();
				}, 2000);
			});
		});

		stickyOffset();
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
