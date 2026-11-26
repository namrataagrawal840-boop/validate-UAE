"""Published figures used for market sizing. Every number carries its source, year and link, and a kind:
"official" (government statistics office), "published" (survey or market report), or "assumption" (our estimate,
shown as such so the user can replace it). Checked November 2026; update as new releases appear."""

S = lambda value, source, year, url, kind="official": dict(value=value, source=source, year=year, url=url, kind=kind)

POPULATION = {  # usual residents
    "All UAE": S(12_060_000, "Federal Competitiveness and Statistics Centre (via Gulf News)", 2025,
                 "https://gulfnews.com/amp/story/uae%2Fuae-population-crosses-12-million-how-many-are-men-and-how-many-women-1.500748187"),
    "Dubai": S(4_580_000, "Dubai Data and Statistics Establishment (via WAM)", 2025, "https://www.wam.ae/en/article/c1hd5qo-dubai-population-tops-4580-million-end-2025"),
    "Abu Dhabi": S(4_140_000, "Statistics Centre Abu Dhabi (via Gulf News)", 2024, "https://gulfnews.com/uae/government/uae-population-hits-113-million-in-2024-1.500261527"),
    "Sharjah": S(2_130_000, "Sharjah Census 2025 (via Khaleej Times)", 2025,
                 "https://www.khaleejtimes.com/uae/sharjah-population-jumps-51-in-10-years-to-reach-213-million-census-shows?amp=1"),
    "Ajman": S(583_000, "Ajman Statistics Centre (via Oxford Business Group)", 2024,
               "https://oxfordbusinessgroup.com/reports/uae-ajman/2025-report/profile/enhanced-development-the-emirate-is-attracting-new-partnerships-and-leveraging-technology-to-solidify-its-position-on-the-global-investment-map-overview/"),
    "Ras Al Khaimah": S(400_000, "Estimate (Bayut population guide)", 2024, "https://bayut.com/mybayut/uae-population-statistics", "published"),
    "Fujairah": S(310_000, "Estimate (Bayut population guide)", 2024, "https://bayut.com/mybayut/uae-population-statistics", "published"),
    "Umm Al Quwain": S(80_000, "Estimate (Bayut population guide)", 2024, "https://bayut.com/mybayut/uae-population-statistics", "published"),
}
GROWTH = {  # yearly population growth
    "Dubai": S(.075, "Dubai Data and Statistics Establishment (via WAM)", 2025, "https://www.wam.ae/en/article/c1hd5qo-dubai-population-tops-4580-million-end-2025"),
    "Abu Dhabi": S(.075, "Statistics Centre Abu Dhabi (via Gulf News)", 2024, "https://gulfnews.com/uae/government/uae-population-hits-113-million-in-2024-1.500261527"),
    "All UAE": S(.07, "FCSC (via Gulf News)", 2025, "https://gulfnews.com/amp/story/uae%2Fuae-population-crosses-12-million-how-many-are-men-and-how-many-women-1.500748187"),
}
WOMEN_SHARE = S(.36, "FCSC (via Gulf News): men 64%, women 36%", 2024, "https://gulfnews.com/uae/government/uae-population-hits-113-million-in-2024-1.500261527")
ADULT_SHARE = S(.82, "Assumption: share of residents aged 18+ (the UAE has a small child population); replace with your own figure", 2025, "", "assumption")
INTERNET = S(.99, "DataReportal Digital 2024: internet penetration", 2024, "https://datareportal.com/reports/digital-2024-united-arab-emirates", "published")
SOCIAL = {
    "Social media users": S(1.0, "DataReportal via Aletihad: 11.3 million social media identities, about 100% of the population", 2025, "https://en.aletihad.ae/news/uae/4557954/javasxript:", "published"),
    "YouTube": S(.736, "Google ad reach via DataReportal/Aletihad: 8.25 million users", 2025, "https://en.aletihad.ae/news/uae/4557954/javasxript:", "published"),
    "Facebook": S(.865, "Meta ad reach via DataReportal/Aletihad: 9.70 million users", 2025, "https://en.aletihad.ae/news/uae/4557954/javasxript:", "published"),
}

# Who uses this kind of product or service (share of the base group), and what they spend.
# low / likely / high so the uncertainty is visible. "base" = which part of the population the share applies to.
CATEGORY = {
    "fitness": dict(base="adults", label="hold a fitness or gym membership",
                    share=(.08, .15, .40), share_src=[
                        S(.082, "Ken Research: paid gym-member penetration", 2022, "https://www.kenresearch.com/healthcare/general-healthcare/uae-fitness-services-market/149539-91.html", "published"),
                        S(.399, "UAE Health & Fitness Industry Report 2026 (survey): adults with a fitness membership", 2026, "https://gymnation.com/health-fitness-report-2026/", "published")],
                    spend=S(600, "GymNation report: median monthly membership across 40 operators (AED)", 2025, "https://gymnation.com/uae-health-fitness-report/", "published")),
    "kitchen": dict(base="adults", label="use food-delivery apps",
                    share=(.30, .42, .55), share_src=[S(.42, "Ken Research: modelled active food-delivery-app users", 2025, "https://www.kenresearch.com/industry-reports/uae-food-delivery-apps-market", "published")],
                    spend=S(114, "Statista: meal-delivery revenue per user US$373 a year (about AED 114 a month)", 2024,
                            "https://statista.com/outlook/emo/online-food-delivery/meal-delivery/united-arab-emirates", "published")),
    "ecommerce": dict(base="online", label="shop online regularly",
                      share=(.35, .467, .60), share_src=[S(.467, "Statista via Khaleej Times: active e-commerce users", 2026,
                                                           "https://www.khaleejtimes.com/business/e-commerce-businesses-regain-confidence-as-sector-sees-101-cagr", "published")],
                      spend=None),
    "education": dict(base="families", label="pay for private tutoring",
                      share=(.30, .47, .66), share_src=[S(.47, "Abu Dhabi Education Council parent survey (40,000 parents)", 2013,
                                                          "https://www.zawya.com/en/business/half-of-parents-surveyed-say-children-receive-private-tutoring-in-abu-dhabi-t511bity", "published")],
                      spend=None),
    "cafe": dict(base="adults", label="drink coffee regularly and buy it out of home",
                 share=(.25, .34, .45), share_src=[S(.57, "Cint survey via Statista: drink coffee regularly", 2018,
                                                     "https://es.statista.com/statistics/920781/united-arab-emirates-regular-beverage-consumption/", "published"),
                                                   S(.60, "Assumption: share of coffee bought out of home (industry estimates 58-60%)", 2023, "https://gitnux.org/uae-coffee-industry-statistics/", "assumption")],
                 spend=None),
    "retail": dict(base="adults", label="buy this kind of product in shops", share=(.15, .30, .50),
                   share_src=[S(.30, "Assumption: depends on the product; replace with a figure for your niche", 2025, "", "assumption")], spend=None),
    "app": dict(base="online", label="would use an app like this", share=(.05, .15, .30),
                share_src=[S(.15, "Assumption: depends on the niche; replace with a figure for your niche", 2025, "", "assumption")], spend=None),
    "services": dict(base="households", label="pay for this kind of service", share=(.15, .25, .40),
                     share_src=[S(.25, "Assumption: depends on the service; replace with a figure for your niche", 2025, "", "assumption")], spend=None),
}
HOUSEHOLD_SIZE = S(4.0, "Assumption: average people per household; replace with your own figure", 2025, "", "assumption")
FAMILY_SHARE = S(.18, "Assumption: share of residents who are parents of school-age children", 2025, "", "assumption")
