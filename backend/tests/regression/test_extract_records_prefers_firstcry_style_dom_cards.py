from __future__ import annotations

from .test_crawl_engine import *  # noqa: F403


@pytest.mark.regression
def test_extract_records_prefers_firstcry_style_dom_cards_over_menu_chrome() -> None:
    html = """
    <html>
      <body>
        <main>
          <ul class="optionav lft">
            <li class="categry inactive">
              <a href="https://www.firstcry.com/club?ref2=menu_dd_catlanding" class="M13_75">
                <img src="https://cdn.fcglcdn.com/brainbees/images/n/club_logo_small.png" alt="FirstCry Club" title="FirstCry Club" />
              </a>
            </li>
            <li class="categry inactive">
              <a href="https://www.firstcry.com/featuredoffer?cpid=7639&ref2=menu_dd_catlanding" class="M13_75">
                <img src="https://cdn.fcglcdn.com/brainbees/images/n/DM-2.gif" alt="Disney Marvel" title="Disney Marvel" />
              </a>
            </li>
          </ul>
          <div class="list_sec fw lft">
            <div class="list_block lft fasnlist">
              <div class="li_inner_block" role="button" tabindex="0" aria-label="Mark &amp; Mia Half Raglan Sleeves Legged Swimsuit - Pink">
                <div class="lblock lft">
                  <div class="list_img wifi">
                    <a href="//www.firstcry.com/mark-and-mia/mark-and-mia-half-raglan-sleeves-legged-swimsuit-pink/21807023/product-detail" target="_blank">
                      <img src="//cdn.fcglcdn.com/brainbees/images/products/300x364/21807023a.webp" alt="Mark &amp; Mia Half Raglan Sleeves Legged Swimsuit - Pink" />
                    </a>
                  </div>
                  <div class="li_txt1 wifi lft">
                    <a href="//www.firstcry.com/mark-and-mia/mark-and-mia-half-raglan-sleeves-legged-swimsuit-pink/21807023/product-detail" target="_blank">
                      Mark &amp; Mia Half Raglan Sleeves Legged Swimsuit - Pink
                    </a>
                  </div>
                  <div class="rupee fw lft" aria-label="Sale price RS 959.2 and Regular price RS 1199">
                    <span class="r1 B14_42">
                      <a aria-label="Sale price RS 959.2" href="//www.firstcry.com/mark-and-mia/mark-and-mia-half-raglan-sleeves-legged-swimsuit-pink/21807023/product-detail" target="_blank">959.2</a>
                    </span>
                    <span class="r2 R12_42">
                      <a aria-label="Regular price RS 1199" href="//www.firstcry.com/mark-and-mia/mark-and-mia-half-raglan-sleeves-legged-swimsuit-pink/21807023/product-detail" target="_blank">
                        <del class="regular-price">1199</del>
                      </a>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.firstcry.com/topoffers?moid=50920&gender=girl,unisex&ref2=menu_dd_girl-fashion_swimming-essentials_H",
        "ecommerce_listing",
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://www.firstcry.com/topoffers?moid=50920&gender=girl,unisex&ref2=menu_dd_girl-fashion_swimming-essentials_H",
            "_source": "dom_listing",
            "title": "Mark & Mia Half Raglan Sleeves Legged Swimsuit - Pink",
            "url": "https://www.firstcry.com/mark-and-mia/mark-and-mia-half-raglan-sleeves-legged-swimsuit-pink/21807023/product-detail",
            "price": "959.2",
            "currency": "INR",
            "image_url": "https://cdn.fcglcdn.com/brainbees/images/products/300x364/21807023a.webp",
        }
    ]

@pytest.mark.regression
def test_extract_records_prefers_sigma_style_product_rows_over_editorial_links() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <section class="resource-list">
            <article>
              <a class="css-by2t45-title" href="/IN/en/technical-documents/technical-article/cell-culture-and-cell-culture-analysis/mammalian-cell-culture/antibiotics-in-cell-culture">
                Article: Why Use Antibiotics in Cell Culture?
              </a>
            </article>
            <article>
              <a class="css-by2t45-title" href="/deepweb/assets/sigmaaldrich/marketing/global/documents/749/633/68966-anti-cancer-antibiotics-flyer-030926-ms.pdf">
                Flyer: Anti-Cancer Antibiotics and Inhibitors in Cancer Research
              </a>
            </article>
          </section>
          <div class="css-a4qnmt-resultsWrapper">
            <div class="css-1vkrqo7-tBodyRow">
              <div class="css-1nu0m23-productNumber">
                <a href="/IN/en/product/sigma/a5955">A5955</a>
              </div>
              <div class="css-13uu5bz-productName">
                <a href="/IN/en/product/sigma/a5955"><b><span>Antibiotic Antimycotic Solution (100×), Stabilized</span></b></a>
              </div>
              <div class="css-18jhhth-description">
                <a href="/IN/en/product/sigma/a5955"><span>suspension, suitable for cell culture, BioReagent</span></a>
              </div>
              <div class="css-26xuj3-pricingColumn">
                <button type="button">View Pricing</button>
              </div>
            </div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.sigmaaldrich.com/IN/en/products/chemistry-and-biochemicals/biochemicals/antibiotics",
        "ecommerce_listing",
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://www.sigmaaldrich.com/IN/en/products/chemistry-and-biochemicals/biochemicals/antibiotics",
            "_source": "dom_listing",
            "title": "Antibiotic Antimycotic Solution (100×), Stabilized",
            "description": "suspension, suitable for cell culture, BioReagent",
            "url": "https://www.sigmaaldrich.com/IN/en/product/sigma/a5955",
        }
    ]

@pytest.mark.regression
def test_extract_records_recovers_listing_price_when_card_uses_currency_code_text() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <article class="product-card">
            <a href="/products/teddy-tshirt">
              <h2>Teddy T-shirt</h2>
            </a>
            <div class="price-copy">GBP 90</div>
            <img src="https://cdn.example.com/teddy.jpg" alt="Teddy T-shirt" />
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/tees",
        "ecommerce_listing",
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/tees",
            "_source": "dom_listing",
            "title": "Teddy T-shirt",
            "url": "https://example.com/products/teddy-tshirt",
            "price": "90",
            "currency": "GBP",
            "image_url": "https://cdn.example.com/teddy.jpg",
        }
    ]

@pytest.mark.regression
def test_extract_records_replaces_generic_item_listing_title_with_product_text() -> (
    None
):
    html = """
    <html>
      <body>
        <div class="thumbnail">
          <h4 class="title">item</h4>
          <a href="/test-sites/e-commerce/allinone/product/1">
            Lenovo ThinkPad X1 Carbon
          </a>
          <p class="description">Lenovo ThinkPad X1 Carbon business laptop</p>
          <h4 class="price">$1,299.00</h4>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://webscraper.io/test-sites/e-commerce/allinone/computers/laptops",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Lenovo ThinkPad X1 Carbon"

@pytest.mark.regression
def test_extract_records_infers_listing_currency_from_locale_path_for_bare_price() -> (
    None
):
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/gb/products/widget"><h2>Widget Prime</h2></a>
          <span class="price">24.99</span>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/gb/products",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "24.99"
    assert rows[0]["currency"] == "GBP"

@pytest.mark.regression
def test_extract_records_ignores_discount_badge_images_inside_listing_cards() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="category-product">
            <div class="image-wrapper grow">
              <img class="offer-tag" src="/media/catalog/category/flat50_tag.png" alt="discount info" />
              <a href="/zivame-satin-pyjama-set-samba.html?productId=874218">
                <img
                  class="prd-grid-image"
                  src="https://cdn.example.com/media/mimages/rb/solid-loader.gif"
                  data-original="https://cdn.example.com/zivame-satin-pyjama-set-samba.jpg"
                  alt="Buy Zivame Satin Pyjama Set - Samba"
                  title="Zivame Satin Pyjama Set - Samba"
                />
              </a>
            </div>
            <div class="product-name">Buy Zivame Satin Pyjama Set - Samba</div>
            <div class="price">₹1148</div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.zivame.com/sleepwear-nightwear/sleep-pyjama-sets.html",
        "ecommerce_listing",
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://www.zivame.com/sleepwear-nightwear/sleep-pyjama-sets.html",
            "_source": "dom_listing",
            "title": "Zivame Satin Pyjama Set - Samba",
            "url": "https://www.zivame.com/zivame-satin-pyjama-set-samba.html?productId=874218",
            "price": "1148",
            "currency": "INR",
            "image_url": "https://cdn.example.com/zivame-satin-pyjama-set-samba.jpg",
        }
    ]

@pytest.mark.regression
def test_extract_records_replaces_review_only_listing_titles_with_product_image_title() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <div class="category-product">
            <div class="image-wrapper grow">
              <a href="/zivame-cup-cake-knit-poly-pyjama-set-1.html?productId=858985">
                <img
                  class="prd-grid-image"
                  src="https://cdn.example.com/zivame-cup-cake-knit-poly-pyjama-set.jpg"
                  alt="Buy Zivame Cup Cake Knit Poly Pyjama Set - Orchid Tint"
                  title="Zivame Cup Cake Knit Poly Pyjama Set - Orchid Tint"
                />
              </a>
            </div>
            <h3 class="product-name">1 reviews given by verified buyers</h3>
            <div class="price">₹775</div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.zivame.com/sleepwear-nightwear/sleep-pyjama-sets.html",
        "ecommerce_listing",
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://www.zivame.com/sleepwear-nightwear/sleep-pyjama-sets.html",
            "_source": "dom_listing",
            "title": "Zivame Cup Cake Knit Poly Pyjama Set - Orchid Tint",
            "url": "https://www.zivame.com/zivame-cup-cake-knit-poly-pyjama-set-1.html?productId=858985",
            "price": "775",
            "currency": "INR",
            "image_url": "https://cdn.example.com/zivame-cup-cake-knit-poly-pyjama-set.jpg",
            "review_count": 1,
        }
    ]

@pytest.mark.regression
def test_extract_records_replaces_review_only_titles_from_lazy_loaded_product_images() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <div class="category-product">
            <div class="image-wrapper grow">
              <a href="/zivame-cup-cake-knit-poly-pyjama-set-1.html?productId=858985">
                <img
                  class="prd-grid-image"
                  src="https://cdn.example.com/media/mimages/rb/solid-loader.gif"
                  data-original="https://cdn.example.com/zivame-cup-cake-knit-poly-pyjama-set.jpg"
                  alt="Buy Zivame Cup Cake Knit Poly Pyjama Set - Orchid Tint"
                  title="Zivame Cup Cake Knit Poly Pyjama Set - Orchid Tint"
                />
              </a>
            </div>
            <h3 class="product-name">1 reviews given by verified buyers</h3>
            <div class="price">₹775</div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.zivame.com/sleepwear-nightwear/sleep-pyjama-sets.html",
        "ecommerce_listing",
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://www.zivame.com/sleepwear-nightwear/sleep-pyjama-sets.html",
            "_source": "dom_listing",
            "title": "Zivame Cup Cake Knit Poly Pyjama Set - Orchid Tint",
            "url": "https://www.zivame.com/zivame-cup-cake-knit-poly-pyjama-set-1.html?productId=858985",
            "price": "775",
            "currency": "INR",
            "image_url": "https://cdn.example.com/zivame-cup-cake-knit-poly-pyjama-set.jpg",
            "review_count": 1,
        }
    ]

@pytest.mark.regression
def test_extract_records_rejects_dom_listing_rows_that_only_have_doc_titles_and_urls() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <article class="category-product">
            <a href="/IN/en/technical-documents/technical-article/cell-culture-and-cell-culture-analysis/mammalian-cell-culture/antibiotics-in-cell-culture">
              Article: Why Use Antibiotics in Cell Culture?
            </a>
          </article>
          <article class="category-product">
            <a href="/deepweb/assets/sigmaaldrich/marketing/global/documents/749/633/68966-anti-cancer-antibiotics-flyer-030926-ms.pdf">
              Flyer: Anti-Cancer Antibiotics and Inhibitors in Cancer Research
            </a>
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.sigmaaldrich.com/IN/en/products/chemistry-and-biochemicals/biochemicals/antibiotics",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_rejects_product_name_placeholder_listing_rows() -> None:
    html = """
    <html>
      <body>
        <main>
          <article class="product-card">
            <a href="/termsofuse">Product Name</a>
            <span class="price">₹0</span>
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.firstcry.com/sets-and--suits/6/166?scat=166&gender=girl,unisex&ref2=menu_dd_girl-fashion_sets-and-suits_H",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_rejects_shipping_only_rendered_listing_rows() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="+CHF16.75 shipping",
                    url="https://example.com/shipping",
                )
            ]
        },
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_rejects_rendered_listing_cta_only_titles() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.discogs.com/sell/list",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Make Offer / Details",
                    url="https://www.discogs.com/sell/item/3970919917?ev=bp_det",
                ),
                _rendered_listing_fragment(
                    title="Widget Prime",
                    url="https://www.discogs.com/products/widget-prime",
                    price="$19.99",
                    image_url="https://www.discogs.com/images/widget-prime.jpg",
                ),
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://www.discogs.com/sell/list",
            "_source": "dom_listing",
            "title": "Widget Prime",
            "price": "19.99",
            "currency": "USD",
            "image_url": "https://www.discogs.com/images/widget-prime.jpg",
            "url": "https://www.discogs.com/products/widget-prime",
        }
    ]

@pytest.mark.regression
def test_extract_records_rejects_job_listing_hub_links_when_structured_job_rows_exist() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@type": "JobPosting",
              "title": "Backend Engineer",
              "url": "/job-123-backend-engineer-at-example-bangalore/"
            },
            {
              "@type": "JobPosting",
              "title": "Data Engineer",
              "url": "/job-456-data-engineer-at-example-remote/"
            }
          ]
        }
        </script>
      </head>
      <body><div id="app"></div></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://jobs.example.com/search-jobs",
        "job_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Jobs in Bangalore",
                    url="https://jobs.example.com/jobs-in-bangalore/",
                ),
                _rendered_listing_fragment(
                    title="Product Academy",
                    url="https://academy.example.com/product/",
                ),
            ]
        },
    )

    assert len(rows) == 2
    assert all(row["_source"] == "structured_listing" for row in rows)
    assert rows[0]["title"] == "Backend Engineer"
    assert (
        rows[0]["url"]
        == "https://jobs.example.com/job-123-backend-engineer-at-example-bangalore/"
    )
    assert rows[1]["title"] == "Data Engineer"
    assert (
        rows[1]["url"]
        == "https://jobs.example.com/job-456-data-engineer-at-example-remote/"
    )

@pytest.mark.regression
def test_extract_records_keeps_job_detail_like_titles_even_when_they_start_with_hub_text() -> (
    None
):
    html = """
    <html>
      <body>
        <article class="job-card">
          <a href="/jobs/backend-engineer-123456">Jobs in Bangalore - Backend Engineer</a>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://jobs.example.com/search",
        "job_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://jobs.example.com/search",
            "_source": "dom_listing",
            "title": "Jobs in Bangalore - Backend Engineer",
            "url": "https://jobs.example.com/jobs/backend-engineer-123456",
        }
    ]

@pytest.mark.regression
def test_extract_records_keeps_job_listing_slug_records_with_numeric_terminal_ids() -> (
    None
):
    html = """
    <html>
      <body>
        <div class="job-listing">
          <a href="/lead-ai-engineer-sherlockdefi-6650681">Lead AI Engineer</a>
        </div>
        <div class="job-listing">
          <a href="/founding-engineer-with-equity-miru-technology-inc-7933051">
            Founding Engineer (with equity)
          </a>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://startup.jobs/",
        "job_listing",
        max_records=10,
    )

    assert len(rows) == 2
    assert rows[0]["title"] == "Lead AI Engineer"
    assert (
        rows[0]["url"] == "https://startup.jobs/lead-ai-engineer-sherlockdefi-6650681"
    )
    assert rows[1]["title"] == "Founding Engineer (with equity)"
    assert (
        rows[1]["url"]
        == "https://startup.jobs/founding-engineer-with-equity-miru-technology-inc-7933051"
    )

@pytest.mark.regression
def test_extract_records_rejects_numeric_non_job_links_on_careers_hosts() -> None:
    html = """
    <html>
      <body>
        <article>
          <a href="https://www.clarkassociatesinc.biz/public-relations/2025-ceo-letter/">
            2025 CEO Letter
          </a>
        </article>
        <article>
          <a href="https://www.clarkassociatesinc.biz/companies/11400/">
            WebstaurantStore
          </a>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://careers.clarkassociatesinc.biz/",
        "job_listing",
        max_records=10,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_ignores_single_page_level_product_payload_on_listing_pages() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "MuscleBlaze",
          "description": "Brand page summary that should not be attached to a single listing row.",
          "brand": {"name": "MuscleBlaze"},
          "image": "https://example.com/brand.png",
          "aggregateRating": {"ratingValue": "4.5", "reviewCount": "132217"},
          "offers": {"priceCurrency": "INR"},
          "url": "/sv/muscleblaze-biozyme-gold-100-whey/SP-129175?navKey=VRNT-250297"
        }
        </script>
      </head>
      <body>
        <article class="product-card">
          <a href="/sv/muscleblaze-pre-workout-wrathx/SP-95398?navKey=VRNT-210726">
            <img src="/w1.png">
            <h2>MuscleBlaze Pre Workout WrathX - 1.12 lb Cola Frost</h2>
          </a>
          <div class="price">Rs. 1999</div>
          <div>235 reviews</div>
        </article>
        <article class="product-card">
          <a href="/sv/muscleblaze-biozyme-gold-100-whey/SP-129175?navKey=VRNT-250297">
            <img src="/w2.png">
            <h2>MuscleBlaze Biozyme Gold 100% Whey</h2>
          </a>
          <div class="price">Rs. 8399</div>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.healthkart.com/brand/muscleblaze?navKey=BR-539",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 2
    assert all(row["_source"] == "dom_listing" for row in rows)
    assert rows[0]["title"] == "MuscleBlaze Pre Workout WrathX - 1.12 lb Cola Frost"
    assert rows[0]["price"] == "1999"
    assert "brand" not in rows[0]
    assert "description" not in rows[0]
    assert rows[1]["title"] == "MuscleBlaze Biozyme Gold 100% Whey"
    assert rows[1]["price"] == "8399"
