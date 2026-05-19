# domx

自分用・非汎用

## インストール

`uv add domx`  
`uv run patchright install chromium`  
`uv run camoufox fetch`

## 使用例

### スクレイピング

```python
from domx import wrap_page
from domx.browser import patchright_page
from domx.utils import append_csv, from_here, save_log, write_bytes

here = from_here(__file__)
save_log(here('log/scraping.log'))

with patchright_page() as page:
    p = wrap_page(page)

    p.goto('https://www.foobarbaz1.jp')
    pref_urls = p.ii('li.item > ul > li > a').urls

    classroom_urls = []
    for i, url in enumerate(pref_urls, 1):
        print(f'pref_urls {i}/{len(pref_urls)}')
        if not p.goto(url):
            append_csv(here('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        classroom_urls.extend(p.ii('.school-area h4 a').urls)

    for i, url in enumerate(classroom_urls, 1):
        print(f'classroom_urls {i}/{len(classroom_urls)}')
        if not p.goto(url):
            append_csv(here('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        th_scan = p.ii('th').scan
        append_csv(here('csv/scrape.csv'), {
            'id': i,
            'URL': page.url,
            '教室名': p.i('h1 .text01').text,
            '住所': p.i('.item .mapText').text,
            '電話番号': p.i('.item .phoneNumber').text,
            'HP': th_scan.m(r'ホームページ').n('td').i('a').url,
            '営業時間': th_scan.m(r'営業時間').n('td').text,
            '定休日': th_scan.m(r'定休日').n('td').text,
        })
        p.i('.school-map').screenshot(here(f'media/{i}-screenshot.png'))
        if (img_url := p.i('.school-area img').src):
            if (res := p.goto(img_url)) and res.ok:
                write_bytes(here(f'media/{i}-img.jpg'), res.body())
```

### スクレイピング(スクショと画像も保存)

```python
import time
from urllib.parse import urlencode

from domx import wrap_page
from domx.browser import patchright_page
from domx.utils import save_log, append_csv, from_here, write_bytes

here = from_here(__file__)
save_log(here('log/scraping.log'))

with patchright_page() as page:
    p = wrap_page(page)
    
    p.goto('https://example.com/demo/search')
    prefecture_urls = p.ii('li > a[href^="https://example.com/demo/search/area/"]').urls

    bukken_urls = []
    for i, prefecture_url in enumerate(prefecture_urls, 1):
        print(f'{i}/{len(prefecture_urls)} エリア一覧ページ')
        page_num = 1
        while True:
            if not p.goto(f'{prefecture_url}?{urlencode({"page": page_num})}'):
                break
            if not (bukken_elems := p.ii('ul li div a[href^="https://example.com"]:has(p)')):
                break
            bukken_urls.extend(bukken_elems.urls)
            page_num += 1
    
    for i, url in enumerate(bukken_urls, 1):
        print(f'{i}/{len(bukken_urls)} 詳細ページ {url}')
        if not p.goto(url):
            append_csv(here('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        
        dt_scan = p.ii('h4').scan.m(r'概要').n('div:has(dl)').ii('dt').scan
        dd_text = lambda pattern: dt_scan.m(pattern).n('dd').text

        append_csv(here('csv/scrape.csv'), {
            'id': i,
            'URL': page.url,
            '価格': dd_text(r'価格'),
            '所在地': dd_text(r'所在地'),
            '交通': dd_text(r'交通'),
            '駐車場': dd_text(r'駐車場'),
            '備考': dd_text(r'備考'),
            '情報更新日': dd_text(r'情報更新日'),
        })
        
        p.ii('h4').scan.m(r'概要').n('div:has(dl)').screenshot(path=here(f'media/{i}-summary.png'))

        elem_iframe = p.i('iframe[src^="https://example.com"]')
        elem_iframe.scroll_into_view()
        time.sleep(3)
        elem_iframe.screenshot(path=here(f'media/{i}-iframe.png'))

        main_img_url = p.i('img.w-full.object-contain').src
        if (body := p.bytes_at(main_img_url)):
            write_bytes(here(f'media/{i}-main-img.jpg'), body)

        img_desc_scan = p.ii('p.text-left').scan.m(r'画像をクリック').n('ul').ii('li p').scan
        img_desc = img_desc_scan.m(r'表紙') or img_desc_scan.m(r'^(?!.*裏面).*')
        img_url = img_desc.o('li').i('a').url
        if (body := p.bytes_at(img_url)):
            write_bytes(here(f'media/{i}-img-desc.jpg'), body)
```

### スクレイピング(HTML丸ごと保存)

```python
from datetime import datetime, timezone

from domx import wrap_page
from domx.browser import camoufox_page
from domx.utils import append_csv, from_here, hash_name, meta_html, save_log, write_text

here = from_here(__file__)
save_log(here('log/scraping.log'))

with camoufox_page() as page:
    p = wrap_page(page)

    p.goto('https://www.foobarbaz1.jp')
    item_urls = p.ii('ul.items > li > a').urls

    for i, url in enumerate(item_urls, 1):
        print(f'item_urls {i}/{len(item_urls)}')
        if not p.goto(url):
            append_csv(here('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        file_name = f'{hash_name(url)}.html'
        html = meta_html({
            'domx:id': i,
            'domx:page_url': page.url,
            'domx:saved_at': datetime.now(timezone.utc),
        }) + page.content()
        if not write_text(here('html') / file_name, html):
            append_csv(here('csv/failed.csv'), {'url': url, 'reason': 'write_text'})
            continue
```

### ローカルHTMLからデータ抽出&Parquet出力

```python
from domx import wrap_parser
from domx.utils import from_here, parse_html, save_log, write_parquet

here = from_here(__file__)
save_log(here('log/scraping.log'))

results = []
for i, file_path in enumerate(here('html').glob('*.html'),1):
    print(f'html {i}')
    if not (parser := parse_html(file_path)):
        continue
    p = wrap_parser(parser)
    dt_scan = p.ii('dt').scan
    results.append({
        'ページURL': p.i('meta[name="domx:page_url"]').attr('content'),
        '保存日時': p.i('meta[name="domx:saved_at"]').attr('content'),
        'ファイル名': file_path.name,
        '教室名': p.i('h1 .text02').text,
        '住所': p.i('.item .mapText').text,
        '所在地': dt_scan.m(r'所在地').n('dd').text,
        '交通': dt_scan.m(r'交通').n('dd').text,
        '物件番号': dt_scan.m(r'物件番号').n('dd').text,
    })
write_parquet(here('parquet/extract.parquet'), results)
```

### ローカルHTMLからデータ抽出&Parquet出力(並列処理)

```python
from pathlib import Path

from domx import wrap_parser
from domx.utils import from_here, glob_paths, parse_html, pool_map, write_parquet

def main():
    here = from_here(__file__)
    html_paths = glob_paths(here('html'), '*.html')
    results = [r for r in pool_map(extract, html_paths) if r]
    write_parquet(here('parquet/extract.parquet'), results)

def extract(file_path: str) -> dict | None:
    if not (parser := parse_html(Path(file_path))):
        return None
    p = wrap_parser(parser)
    dt_scan = p.ii('dt').scan
    return {
        'ページURL': p.i('meta[name="domx:page_url"]').attr('content'),
        '保存日時': p.i('meta[name="domx:saved_at"]').attr('content'),
        'ファイルパス': file_path,
        '教室名': p.i('h1 .text02').text,
        '住所': p.i('.item .mapText').text,
        '所在地': dt_scan.m(r'所在地').n('dd').text,
        '交通': dt_scan.m(r'交通').n('dd').text,
        '価格': dt_scan.m(r'価格').n('dd').text,
        '設備・条件': dt_scan.m(r'設備').n('dd').text,
        '備考': dt_scan.m(r'備考').n('dd').text,
    }

if __name__ == '__main__':
    main()
```

## License - ライセンス

[MIT](./LICENSE)
