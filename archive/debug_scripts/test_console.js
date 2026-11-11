const puppeteer = require("puppeteer");
(async () => {
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();
  page.on("console", msg => console.log("BROWSER:", msg.text()));
  page.on("pageerror", error => console.log("ERROR:", error.message));
  await page.goto("http://localhost:8000");
  await page.waitForTimeout(3000);
})();
