"""
Словник ризиків великих харчових компаній.

Призначення: текстовий аналіз розділів Risk Factors у річних звітах

Структура: {категорія: {підкатегорія: [терміни]}}

Правила запису термінів:
- усі терміни англійською та в нижньому регістрі — пошук має бути
нечутливим до регістру;
- "*" в кінці терміна означає основу слова: "tariff*" охоплює
tariff, tariffs, tariffed;
- термін без "*" шукається лише як ціле слово або фраза
("import" не має збігатися з "important");
- пробіл і дефіс у фразах взаємозамінні ("plant-based" = "plant based");
- терміни підібрано так, щоб уникати поширених хибних збігів
(напр. немає окремого "trade", "conflict", "union", "climate", "plant").
"""

RISK_DICTIONARY = {

    # Макроекономіка та ринкові умови
    "Macroeconomic and Market Conditions": {
        "Inflation": [
            "inflation", "inflationary", "deflation*", "hyperinflation*",
            "cost of living", "stagflation",
        ],
        "Economic downturn and consumer spending": [
            "recession*", "economic downturn*", "economic slowdown*",
            "economic uncertainty", "economic condition*", "economic crisis",
            "unemployment", "consumer confidence", "consumer spending",
            "discretionary spending", "disposable income",
        ],
        "Interest rates and financial markets": [
            "interest rate*", "monetary policy", "credit market*",
            "capital market*", "financial market*", "market volatility",
        ],
        "Foreign exchange": [
            "foreign currency", "foreign exchange", "exchange rate*",
            "currency fluctuation*", "currency translation", "currency risk*",
            "devaluation*", "strength of the u.s. dollar",
            "stronger u.s. dollar", "strengthening of the u.s. dollar",
        ],
        "Emerging markets": [
            "emerging market*", "developing market*",
        ],
    },

    # Ціни на сировину та ресурси
    "Commodity and Input Prices": {
        "General input costs": [
            "commodity", "commodities", "commodity price*", "commodity cost*",
            "raw material*", "input cost*", "ingredient cost*",
            "cost of goods sold", "price volatility", "cost inflation",
            "input cost inflation", "supply cost*",
        ],
        "Agricultural commodities": [
            "cocoa", "sugar", "high fructose corn syrup", "sweetener*",
            "wheat", "flour", "corn", "oats", "soybean*", "dairy", "milk",
            "butter", "cheese", "vegetable oil*", "edible oil*", "palm oil",
            "coffee", "peanut*", "almond*", "hazelnut*", "tree nuts",
            "poultry", "pork", "beef", "eggs", "tomatoes", "potatoes",
            "juice concentrate*", "orange juice", "grains",
        ],
        "Packaging materials": [
            "packaging material*", "packaging cost*", "aluminum",
            "aluminium", "steel", "tinplate", "resin*", "pet bottle*",
            "pet resin", "plastic packaging", "corrugate*", "cardboard",
            "paperboard", "glass bottle*",
        ],
        "Energy and transport costs": [
            "energy cost*", "energy price*", "natural gas", "electricity",
            "fuel cost*", "fuel price*", "diesel", "oil price*",
            "freight cost*", "transportation cost*", "logistics cost*",
        ],
        "Hedging": [
            "hedg*", "derivative instrument*", "futures contract*",
            "forward contract*", "mark-to-market",
        ],
    },

    # Конкуренція
    "Competition": {
        "Competitive intensity": [
            "competition", "competitive", "competitor*", "compete*",
            "market share", "new entrant*", "emerging brand*",
            "smaller brand*", "insurgent brand*", "local brand*",
            "regional brand*",
        ],
        "Private label": [
            "private label*", "private-label", "store brand*", "own brand*",
            "own-label", "retailer brand*",
        ],
        "Price and promotion pressure": [
            "pricing pressure", "price competition", "competitive pricing",
            "promotional activit*", "promotional spending",
            "promotional pressure", "price gap*", "discounting",
        ],
        "Innovation pressure": [
            "failure to innovate", "ability to innovate",
            "successfully innovate", "keep pace with",
            "new product introduction*", "successful new product*",
            "product innovation",
        ],
    },

    # Клієнти, ритейл і канали збуту
    "Customers, Retail and Distribution Channels": {
        "Customer concentration": [
            "largest customer*", "significant customer*", "key customer*",
            "major customer*", "customer concentration",
            "concentration of customer*", "walmart", "wal-mart", "costco",
            "kroger", "amazon", "ahold", "tesco", "carrefour",
            "dollar general",
        ],
        "Retail consolidation and bargaining power": [
            "retail consolidation", "consolidation in the retail",
            "consolidation of retail*", "consolidation among retail*",
            "bargaining power", "negotiating leverage",
            "negotiating strength", "retail customer*", "shelf space",
            "retailer inventor*", "inventory level*", "destock*",
            "inventory reduction*",
        ],
        "Channel shifts": [
            "e-commerce", "ecommerce", "online retail*", "omnichannel",
            "direct-to-consumer", "discounter*", "club store*",
            "dollar store*", "convenience store*", "away-from-home",
            "foodservice", "food service", "quick service restaurant*",
            "channel shift*",
        ],
        "Bottlers and distributors": [
            "bottler*", "bottling partner*", "bottling system",
            "franchise bottler*", "franchised bottler*", "distributor*",
            "independent distributor*", "direct-store-delivery",
            "direct store delivery", "dsd",
        ],
    },

    # Споживчі вподобання та тренди здоров'я
    "Consumer Preferences and Health Trends": {
        "Changing preferences": [
            "consumer preference*", "consumer taste*", "consumer trend*",
            "changing consumer", "changes in consumer", "shift in consumer",
            "shifts in consumer", "consumer demand", "consumer behavior",
            "consumer behaviour", "purchasing pattern*",
            "consumption pattern*", "eating habit*", "dietary habit*",
        ],
        "Health and wellness": [
            "health and wellness", "healthier", "nutrition*", "nutritional",
            "obesity", "diabetes", "sugar consumption", "sugar content",
            "reduced sugar", "low-sugar", "added sugar*", "calorie*",
            "sodium", "saturated fat", "fat content", "ultra-processed",
            "ultraprocessed", "processed food*", "artificial ingredient*",
            "clean label", "natural ingredient*",
        ],
        "GLP-1 and weight-loss drugs": [
            "glp-1", "glp1", "weight loss drug*", "weight-loss drug*",
            "weight loss medication*", "weight-loss medication*",
            "weight management drug*", "weight management medication*",
            "appetite suppress*", "semaglutide", "ozempic", "wegovy",
            "tirzepatide", "mounjaro", "zepbound", "anti-obesity",
        ],
        "Plant-based and alternatives": [
            "plant-based", "dairy alternative*", "dairy-free", "non-dairy",
            "oat drink*", "oat-based", "vegan", "flexitarian",
            "meat alternative*", "alternative protein*",
        ],
        "Demographics": [
            "demographic*", "aging population", "ageing population",
            "millennial*", "gen z", "generation z", "household size",
            "multicultural", "birth rate*",
        ],
        "Value seeking and price sensitivity": [
            "value-seeking", "trade down", "trading down", "trade-down",
            "price elasticity", "price sensitiv*", "value-conscious",
            "budget-conscious", "affordability",
        ],
    },

    # Репутація та бренд
    "Reputation and Brand": {
        "Brand image and reputation": [
            "reputation*", "reputational", "brand image",
            "brand reputation", "brand value", "brand equity",
            "brand loyalty", "consumer trust", "public perception",
            "perception of our brand*",
        ],
        "Publicity and social media": [
            "negative publicity", "adverse publicity",
            "unfavorable publicity", "unfavourable publicity",
            "social media", "viral", "influencer*", "misinformation",
            "disinformation", "false information", "negative comments",
            "media coverage",
        ],
        "Boycotts and activism": [
            "boycott*", "consumer activism", "activist group*",
            "political or social issue*", "social or political issue*",
            "controversial", "polariz*", "polaris*",
        ],
        "Marketing effectiveness": [
            "marketing effectiveness", "advertising effectiveness",
            "effectiveness of our marketing",
            "effectiveness of our advertising", "marketing investment*",
            "marketing campaign*", "sponsorship*", "endorsement*",
            "celebrit*",
        ],
        "Stakeholder expectations": [
            "stakeholder expectation*", "esg", "greenwashing",
            "social responsibility", "corporate responsibility",
            "sustainability commitment*",
        ],
    },

    # Регулювання та право
    "Regulation and Legal": {
        "General regulation": [
            "regulation*", "regulatory", "legislation", "legislative",
            "laws and regulations", "rulemaking", "regulator*",
            "government action*", "government polic*", "executive order*",
        ],
        "Food, nutrition and ingredient regulation": [
            "fda", "food and drug administration", "usda", "fsma",
            "food safety modernization act", "labeling", "labelling",
            "nutrition label*", "front-of-package", "front-of-pack",
            "health claim*", "nutrient profil*",
            "generally recognized as safe", "gras", "food additive*",
            "color additive*", "colour additive*", "artificial dye*",
            "artificial color*", "food dye*", "synthetic dye*", "red dye",
            "red no. 3", "titanium dioxide", "maha",
            "make america healthy again", "dietary guidelines",
            "school meal*", "snap benefit*", "snap program*",
            "supplemental nutrition assistance", "efsa", "novel food*",
        ],
        "Sugar and food taxes": [
            "sugar tax*", "soda tax*", "beverage tax*",
            "sweetened beverage tax*", "sugar-sweetened beverage*",
            "excise tax*", "sin tax*", "junk food tax*", "health tax*",
        ],
        "Marketing and advertising restrictions": [
            "marketing to children", "advertising to children",
            "advertising restriction*", "marketing restriction*",
            "restrictions on advertising", "restrictions on marketing",
            "warning label*", "warning statement*", "prop 65",
            "proposition 65",
        ],
        "Packaging regulation": [
            "extended producer responsibility", "epr", "deposit return",
            "container deposit", "bottle bill*", "single-use plastic*",
            "packaging regulation*", "packaging law*", "plastic tax*",
            "tethered cap*", "ppwr",
        ],
        "Litigation": [
            "litigation", "lawsuit*", "class action*", "legal proceeding*",
            "legal claim*", "consumer protection", "false advertising",
            "deceptive", "jury verdict*", "adverse judgment*",
            "government investigation*", "subpoena*",
        ],
        "Antitrust": [
            "antitrust", "anti-trust", "competition law*",
            "competition authorit*", "ftc", "federal trade commission",
            "merger review",
        ],
        "Anti-corruption and ethics": [
            "bribery", "corruption", "fcpa", "foreign corrupt practices",
            "anti-bribery", "anti-corruption", "money laundering",
            "fraudulent", "unethical", "misconduct",
        ],
    },

    # Податки
    "Tax": {
        "Tax law changes": [
            "tax law*", "tax legislation", "tax reform", "tax rate*",
            "effective tax rate", "tax cuts and jobs act",
            "one big beautiful bill", "inflation reduction act",
            "corporate minimum tax", "tax polic*",
        ],
        "International tax": [
            "pillar two", "global minimum tax", "oecd", "base erosion",
            "transfer pricing", "digital services tax*", "repatriat*",
        ],
        "Tax disputes and audits": [
            "tax audit*", "tax authorit*", "tax dispute*", "irs",
            "internal revenue service", "uncertain tax position*",
            "tax assessment*", "tax examination*", "tax court",
        ],
    },

    # Кібербезпека та захист даних
    "Cybersecurity and Data Privacy": {
        "Cyber threats": [
            "cyber*", "hacker*", "hacking", "ransomware", "malware",
            "phishing", "computer virus*", "data breach*",
            "security breach*", "security incident*", "unauthorized access",
            "denial of service", "social engineering",
        ],
        "IT systems and outages": [
            "information technology system*", "it system*",
            "information system*", "system failure*", "system outage*",
            "service outage*", "it outage*", "service interruption*",
            "third-party service provider*", "cloud-based",
            "cloud service*", "crowdstrike",
        ],
        "Data privacy": [
            "data privacy", "privacy", "personal data",
            "personal information", "data protection", "gdpr",
            "general data protection regulation", "ccpa",
            "california consumer privacy act", "consumer data",
            "data localization",
        ],
    },

    # ШІ та технологічні зміни
    "AI and Technological Change": {
        "Artificial intelligence": [
            "artificial intelligence", "ai", "generative ai", "gen ai",
            "machine learning", "large language model*", "algorithm*",
            "ai act",
        ],
        "Automation and digital transformation": [
            "automation", "robotic*", "digital transformation",
            "digitization", "digitalization", "digitalisation",
            "digital capabilit*", "data analytics", "digital tool*",
        ],
        "Technological change": [
            "technological change*", "technological development*",
            "technological advance*", "emerging technolog*",
            "new technolog*", "disruptive technolog*",
            "technology investment*",
        ],
        "System implementation": [
            "erp", "enterprise resource planning",
            "system implementation*", "system upgrade*",
            "systems transition", "implementation of new system*",
        ],
    },

    # Інтелектуальна власність
    "Intellectual Property": {
        "IP protection": [
            "intellectual property", "trademark*", "trade mark*",
            "patent*", "copyright*", "trade secret*", "trade dress",
            "proprietary rights", "proprietary information",
            "proprietary technolog*", "proprietary formula*",
            "secret formula*", "know-how", "brand protection",
        ],
        "Infringement and counterfeiting": [
            "infringe*", "counterfeit*", "imitation*", "misappropriat*",
            "copycat*",
        ],
        "Licensing": [
            "license agreement*", "licensing agreement*",
            "licensing arrangement*", "licensed brand*", "royalt*",
        ],
    },

    # Геополітика
    "Geopolitics": {
        "War and armed conflict": [
            "war", "wars", "warfare", "acts of war", "armed conflict*",
            "military conflict*", "military action*", "regional conflict*",
            "international conflict*", "geopolitical conflict*",
            "hostilities", "invasion", "terroris*",
        ],
        "Specific regions": [
            "ukraine", "russia*", "israel", "gaza", "middle east", "iran",
            "red sea", "taiwan", "u.s.-china", "venezuela",
        ],
        "Political instability": [
            "geopolitical", "political instability", "political unrest",
            "political uncertainty", "civil unrest", "social unrest",
            "coup", "coups", "government instability", "nationaliz*",
            "expropriat*", "political condition*",
        ],
        "Sanctions": [
            "economic sanction*", "international sanction*",
            "trade sanction*", "sanctions against", "sanctions imposed",
            "sanctions regime*", "sanctioned", "embargo*", "ofac",
            "restrictive measure*",
        ],
    },

    # Міжнародна торгівля
    "Trade": {
        "Tariffs and duties": [
            "tariff*", "retaliatory", "import dut*", "customs dut*",
            "countervailing", "anti-dumping", "section 232",
            "section 301", "ieepa", "de minimis",
        ],
        "Trade policy and agreements": [
            "trade war*", "trade polic*", "trade barrier*",
            "trade restriction*", "trade dispute*", "trade agreement*",
            "trade relation*", "trade tension*", "free trade agreement*",
            "protectionism", "protectionist", "usmca", "nafta",
        ],
        "Imports and exports": [
            "import", "imports", "imported", "importation", "export",
            "exports", "exported", "export control*", "import quota*",
            "export quota*", "cross-border", "country of origin",
        ],
    },

    # Клімат і довкілля
    "Climate and Environment": {
        "Physical climate risk": [
            "climate change", "climate-related", "changing climate",
            "climate risk*", "extreme weather", "weather condition*",
            "weather event*", "adverse weather", "natural disaster*",
            "drought*", "flood*", "hurricane*", "wildfire*",
            "heat wave*", "heatwave*", "rising temperature*",
            "severe storm*", "tropical storm*", "winter storm*", "frost",
            "el nino", "el niño", "la nina", "la niña", "water scarcity",
            "water stress", "water availability",
        ],
        "Transition risk and carbon": [
            "greenhouse gas", "ghg", "carbon emission*", "emissions",
            "net zero", "net-zero", "carbon tax*", "carbon pric*",
            "decarboniz*", "decarbonis*", "low-carbon",
            "renewable energy", "science based target*", "sbti",
            "scope 3",
        ],
        "Sustainability disclosure rules": [
            "climate disclosure*", "climate-related disclosure*", "csrd",
            "corporate sustainability reporting directive", "issb",
            "sustainability reporting", "sb 253", "sb 261",
        ],
        "Nature, water and waste": [
            "deforestation", "eudr", "biodiversity",
            "regenerative agriculture", "land use", "soil health",
            "water use", "water usage", "wastewater", "pollution",
            "packaging waste", "plastic waste", "plastic pollution",
            "recycl*", "food waste", "environmental law*",
            "environmental regulation*", "hazardous substance*",
            "hazardous material*",
        ],
        "Sustainability goals": [
            "sustainability goal*", "sustainability target*",
            "environmental goal*", "esg goal*", "climate goal*",
            "climate target*",
        ],
    },

    # Операційна діяльність і ланцюги постачання
    "Operations and Supply Chain": {
        "Suppliers and sourcing": [
            "supply chain*", "supplier*", "sole source*",
            "single source*", "sole supplier*", "single supplier*",
            "limited number of supplier*", "co-manufactur*",
            "contract manufactur*", "third-party manufactur*",
            "co-packer*", "vendor*",
        ],
        "Disruptions and shortages": [
            "supply disruption*", "supply chain disruption*",
            "operational disruption*", "production disruption*",
            "business disruption*", "business interruption*",
            "supply interruption*", "production interruption*",
            "supply shortage*", "material shortage*",
            "ingredient shortage*", "product shortage*",
            "supply constraint*", "bottleneck*", "force majeure",
            "out-of-stock*",
        ],
        "Manufacturing": [
            "manufacturing facilit*", "manufacturing plant*",
            "production plant*", "processing plant*",
            "production facilit*", "manufacturing operation*",
            "production capacity", "manufacturing capacity",
            "capacity constraint*", "equipment failure*",
            "equipment breakdown*", "mechanical breakdown*",
            "industrial accident*", "fire", "fires", "explosion*",
            "production line*",
        ],
        "Logistics": [
            "logistic*", "transportation", "freight", "shipping",
            "trucking", "truck driver*", "railroad*", "rail service*",
            "ports", "port congestion", "port strike*", "warehous*",
            "distribution center*", "distribution centre*",
            "freight carrier*", "third-party carrier*",
            "shipping container*", "container shortage*",
        ],
    },

    # Безпечність і якість продукції
    "Product Safety, Quality and Liability": {
        "Recalls and quality": [
            "product safety", "food safety", "product quality",
            "quality control", "quality assurance", "quality issue*",
            "recall*", "market withdrawal*", "product withdrawal*",
        ],
        "Contamination and hazards": [
            "contaminat*", "adulterat*", "tamper*", "foreign material*",
            "foreign object*", "allergen*", "undeclared", "mislabel*",
            "pathogen*", "salmonella", "listeria", "e. coli", "e coli",
            "botulism", "aflatoxin*", "mycotoxin*", "heavy metal*",
            "lead levels", "lead content", "cadmium", "arsenic", "pfas",
            "forever chemical*", "bpa", "bisphenol", "microplastic*",
            "acrylamide", "benzene", "mineral oil hydrocarbon*",
            "foodborne illness*", "food-borne illness*",
        ],
        "Product liability": [
            "product liability", "liability claim*", "personal injury",
            "illness or injury", "injury or illness", "spoilage",
        ],
    },

    # Сільськогосподарські та біологічні загрози
    "Agricultural and Biological Hazards": {
        "Crops and harvests": [
            "crops", "crop yield*", "crop disease*", "crop failure*",
            "poor harvest*", "harvest*", "plant disease*", "pests",
            "pest infestation*", "infestation*", "agricultural",
            "growing condition*", "growing region*", "swollen shoot",
            "black pod",
        ],
        "Animal diseases and welfare": [
            "livestock", "animal disease*", "avian influenza",
            "avian flu", "bird flu", "h5n1", "african swine fever",
            "foot-and-mouth", "animal welfare", "cage-free",
        ],
        "Agricultural inputs and GMO": [
            "gmo", "gmos", "genetically modified", "bioengineered",
            "pesticide*", "glyphosate", "herbicide*", "fertilizer*",
            "fertiliser*",
        ],
    },

    # Фінансова стійкість
    "Financial Resilience": {
        "Debt and liquidity": [
            "indebtedness", "debt", "financial leverage", "leverage ratio*",
            "highly leveraged", "borrowing*", "liquidity",
            "credit facilit*", "revolving credit", "commercial paper",
            "refinanc*", "covenant*", "credit rating*", "rating agenc*",
            "downgrade*", "cost of capital", "cost of borrowing",
            "access to capital",
        ],
        "Impairments": [
            "impairment*", "goodwill", "intangible asset*", "write-down*",
            "write-off*", "indefinite-lived", "carrying value*",
        ],
        "Pensions and benefit obligations": [
            "pension*", "postretirement", "post-retirement",
            "defined benefit", "multiemployer", "multi-employer",
            "retirement plan*",
        ],
        "Counterparty risk": [
            "counterparty", "counterparties", "credit risk",
            "bank failure*", "financial institution*", "credit loss*",
        ],
        "Insurance": [
            "insurance coverage", "insurance cost*", "insurance premium*",
            "uninsured", "underinsured", "self-insur*",
            "adequately insured",
        ],
        "Shareholder returns": [
            "dividend*", "share repurchase*", "stock repurchase*",
            "buyback*",
        ],
        "Losses and going concern": [
            "going concern", "substantial doubt", "net loss*",
            "accumulated deficit", "history of losses",
            "achieve profitability", "return to profitability",
            "cash burn", "additional financing", "additional capital",
            "convertible note*", "dilution", "dilutive",
        ],
    },

    # Стратегічні угоди та трансформація
    "Strategic Transactions and Transformation": {
        "Mergers and acquisitions": [
            "acquisition*", "acquired business*", "merger*",
            "integration of acquired", "integrate acquired",
            "successfully integrate", "integration risk*", "synerg*",
            "strategic transaction*", "business combination*",
        ],
        "Divestitures and separations": [
            "divestiture*", "divest*", "disposition*", "spin-off*",
            "spinoff*", "planned separation", "proposed separation",
            "the separation", "strategic alternative*",
            "portfolio reshaping",
        ],
        "Restructuring and cost programs": [
            "restructuring", "reorganization", "reorganisation",
            "cost savings", "cost-saving", "productivity initiative*",
            "productivity program*", "transformation program*",
            "transformation initiative*", "business transformation",
            "efficiency program*", "plant closure*", "facility closure*",
            "headcount reduction*", "workforce reduction*", "layoff*",
        ],
        "Strategy execution": [
            "strategic plan*", "strategic initiative*", "growth strateg*",
            "strategic priorit*", "failure to execute",
            "execute our strategy", "long-term strategy",
        ],
    },

    # Людський капітал і праця
    "Human Capital and Labor": {
        "Talent and key personnel": [
            "talent", "key personnel", "key employee*", "management team",
            "senior management", "executive officer*", "succession",
            "attract and retain", "attract, develop and retain",
            "retention of key", "employee retention", "recruit*",
            "skilled employee*", "qualified personnel",
            "leadership transition*",
        ],
        "Labor market and costs": [
            "labor shortage*", "labour shortage*", "labor cost*",
            "labour cost*", "wages", "wage inflation", "wage rate*",
            "wage increase*", "minimum wage", "benefit cost*",
            "healthcare cost*", "health care cost*", "employee benefit*",
            "tight labor market", "labor availability", "labor market*",
            "qualified workforce",
        ],
        "Unions and labor relations": [
            "labor union*", "trade union*", "unions", "unionized",
            "unionization", "union representation",
            "collective bargaining", "labor dispute*", "labour dispute*",
            "labor strike*", "strikes", "work stoppage*",
            "labor relations", "works council*", "labor unrest",
            "labor agreement*",
        ],
        "Workplace health and safety": [
            "workplace safety", "occupational safety",
            "occupational health", "employee safety",
            "health and safety", "workplace injur*",
        ],
        "Culture and DEI": [
            "corporate culture", "company culture", "our culture",
            "diversity and inclusion", "diversity, equity", "dei",
            "workforce diversity", "employee engagement", "remote work",
            "hybrid work", "return to office",
        ],
    },

    # Пандемії та громадське здоров'я
    "Pandemics and Public Health": {
        "Pandemics and outbreaks": [
            "pandemic*", "epidemic*", "covid*", "coronavirus",
            "sars-cov-2", "disease outbreak*", "outbreak of disease",
            "outbreaks of disease", "viral outbreak*", "influenza",
            "infectious disease*", "contagious disease*",
            "communicable disease*", "mpox", "measles",
        ],
        "Public health measures": [
            "public health", "health crisis", "health crises",
            "health emergenc*", "quarantine*", "lockdown*",
            "stay-at-home", "social distancing", "travel restriction*",
            "vaccine*", "vaccination*",
        ],
    },

    # Корпоративне управління та акціонери
    "Governance and Shareholder Structure": {
        "Activism and control": [
            "activist investor*", "activist shareholder*",
            "shareholder activism", "proxy contest*", "proxy fight*",
            "shareholder proposal*", "controlling stockholder*",
            "controlling shareholder*", "voting control", "voting power",
            "dual class", "class b common stock", "hershey trust",
            "milton hershey school", "majority shareholder*",
            "principal shareholder*", "anti-takeover",
            "takeover attempt*", "takeover bid*", "hostile takeover*",
        ],
        "Stock price and listing": [
            "stock price volatility", "market price of our",
            "price of our common stock", "trading price",
            "american depositary", "delist*", "nasdaq listing",
            "short seller*", "foreign private issuer",
            "emerging growth company",
        ],
        "Internal controls": [
            "internal control over financial reporting",
            "internal controls", "material weakness*", "sarbanes-oxley",
            "corporate governance", "restatement*",
        ],
    },

    # Права людини та соціальні питання
    "Human Rights and Social Issues": {
        "Labor rights in supply chain": [
            "human rights", "child labor", "child labour", "forced labor",
            "forced labour", "modern slavery", "human trafficking",
            "labor practices", "labour practices",
            "uyghur forced labor prevention act", "uflpa",
        ],
        "Responsible sourcing and farmers": [
            "responsible sourcing", "ethical sourcing",
            "sustainable sourcing", "fair trade", "fairtrade",
            "living income", "smallholder*", "farmer livelihood*",
            "farmer income*", "farming communit*",
        ],
        "Due diligence rules": [
            "supply chain due diligence", "human rights due diligence",
            "csddd", "corporate sustainability due diligence",
            "supply chain act", "lksg",
        ],
        "Communities": [
            "community relations", "local communit*", "indigenous",
            "social license", "community opposition",
        ],
    },
}