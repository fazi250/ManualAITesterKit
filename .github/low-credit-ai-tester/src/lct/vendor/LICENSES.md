# Third-party code in `page-controller.js`

`page-controller.js` is an unmodified esbuild IIFE bundle (global `LctPageController`) of:

| Package | Version | License | Copyright |
|---|---|---|---|
| [@page-agent/page-controller](https://github.com/alibaba/page-agent) | 1.12.4 | MIT | 2026 SimonLuvRamen; 2026 Alibaba Group Holding Limited |
| [ai-motion](https://github.com/gaomeng1900/ai-motion) | 0.4.8 | MIT | 2025 Simon \<gaomeng1900@gmail.com\> |

page-agent states that its DOM processing is derived from [browser-use](https://github.com/browser-use/browser-use) (MIT, Copyright 2024 Gregor Zunic).

Rebuild:
```
npm install @page-agent/page-controller@1.12.4 esbuild
echo export { PageController } from '@page-agent/page-controller'; > entry.js
npx esbuild entry.js --bundle --format=iife --global-name=LctPageController --minify --legal-comments=eof --outfile=page-controller.js
```

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
