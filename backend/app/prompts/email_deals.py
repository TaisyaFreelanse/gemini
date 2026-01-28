# Промпт для витягування угод з листів (French coupon site, email letters).
# Placeholders: [EMAIL] — тіло листа, {domain} — домен для поля domain у виході.

EMAIL_DEALS_PROMPT = """
From email letters extract deals with or without promo codes in French language for coupon website. Keep strictly to the content of the letters, do not imagine any information. Do not compose deals without some special price, gift or without discount in percentage, do not compose deals about new collections, products or opening new branches. Not repeat text inside deals of one shop in description field, all deals should have a unique description. If the letter comes from affiliate network it could contain many deals, you should select only deals for French (FR) or worldwide market (WW). If the shop has many deals do not write its name in every deal description also do not compose more then six deals for one shop, but remember when the email from Monbon or affiliate network (CPA) you must do as much deals and codes as are in the email. You should prepare all the data for the deal and split it to appointed fields. Take into account the subject of letters as the information about promo code itself and its conditions could be in the subject.

If any field is not found, its value should be exactly "Не знайдено" (in ukrainian language).

Write the deal only for the shop from which is the e-mail.

Desired Fields:

shop: name of shop. Many e-mails are re-send from Monbon and CPA partners remember this when indicating the name of shop, not write the name of Monbon or partner affiliate networks in the deals.

domain: domain name of shop.

description: This is the main text which visitor sees, this text should attract him and motivate him to click the button and see the deal on the advertiser's website. That is why it should contain any numbers, which could be used as a low price deal or like a procentage of discount or amount of discount. If the deal is for a free delivery, appoint the amount necessary for it in this field. Appoint the subject of discount (the services or the products or category of products) in this field, it is important that visitor sees for what is the deal in that text. Text should be short, maximum 60 symbols. If there is the name of campaign or sale (like, Winter sale, Halloween etc), it should be appointed in the beginning of text, the discount should be next, if no special campaign with name, then the text should be started with discount or words like: Obtenez, Profitez, Bénéficiez, Economisez, Jouissez. Compose deals using synonymous words for the same shop. Never write in this field the promo code itself or the dates of its validity (except names of holidays). Instead of promo code itself (if it is deal with promo code), we write: avec ce code promo, grâce à ce code promo, en saisissant ce code promo, en ajoutant ce code promo. The name of shop we always use at once after words code promo, not dividing it with any words. Example: avec ce code promo Armani. We never write about limitations in this field or amounts of order necessary for the deal, except of free delivery where we write the order amount necessary for it. In the end do not write punctuation marks. The sentence begins with capital. The euro and dollar always write as €, $ not in words. Do not leave space before signs like these: %, $,€, ! (example 30%, 20€). In amounts, if necessary, use "." not "," (ex.: 39.99€, not 39,99€). Never write amount of discount without words réduction, rabais, remise. If you use the name of shop without words promo code put before chez or sur, depending on rules of grammar (ex.: avec ce code promo Armani, sur les parfums féminins chez Armani).

full_description: In this field we write the exclusions from deal, the demands to receive the discount and other limitation or negative information, except the time of validity of deal, which you should appoint in the field date_end. Text maximum 160 symbols. We should appoint in that field in which cases the deal or promo code does not work or for which brands or goods it is not applicable (from the information in the letter). If there are no additional conditions this field could be left empty.

code: a word or a set of letters and numbers that you can use to get a discount. Here should be written only code, without any other words. The code should be taken only from the letter text or image otherwise this field should be "Не знайдено".

date_start: Timestamp (exactly Y-M-D Hr:Min) when promo code or action becomes active. Never write the past date in this field.

date_end: Timestamp (exactly Y-M-D Hr:Min) when promo code or action becomes inactive. If the date is indicated with day of week you should calculate the date_end according to the date of the next appoined day of week in the letter. If no date_end could be found in the letter always write the date of the next day of date_start.

offer_type: offer type must be appointed like one number from the appointed here: 1 when deal with promo code, 2 code for delivery, 3 deal for delivery, 4 deal with discount less 50% and when it is not written sale, 6 deal with discount more than 50% or when written sale, 7 deal or code with a gift, 9 code for first order for a new customer.

target_url: this the url to a page with the appointed deal, which is shown in letter from the shop itself and not from affiliate partner network (CPA), it should include the name of domain. If the link has any utm tag, you should cut it and give only the link without such tags.

click_url: in this field should be written "Не знайдено".

discount: in this field should be appointed the discount itself and % or currency in which the discount. Allowed currencies: Euro. Never indicate in this field the price after discount or any price from the sale, only should be appointed the amount of discount. If there is no discount in this field should be written "Не знайдено". In this field never write minus or "-" or any other letters, only numbers and % or currency.

categories: category ID must be a number that matches the deal/promo code. There could be multiple categories/numbers. Allowed categories are: 32 Education & Hobbits, 31 Propositions Entreprises, 30 Gadgets, 29 Accessoires de mode, 28 Luminaires & Décoration, 27 Articles pour femmes enceintes, 26 Hi-fi Vidéo Instruments, 25 Bricolage, 24 Jardin & Fleuriste, 23 Chaussures, 22 Charme & Lingerie, 21 Santé & Bien-être & CBD, 20 Vidéo & Jeux en ligne, 19 Articles pour la Maison, 18 Sport & Fitness, 16 Electroménager, 15 Vacances & Voyage, 14 Eco / Bio Naturel, 13 Meuble & Literie, 12 Alimentation & Vins, 11 Beauté & Cosmetique, 10 Livres / CD / DVD, 9 Photo & Affiches, 8 Bijouterie Montres, 7 Animaux, 6 Logiciels Internet Photobank, 5 Electronique, 4 Fleurs & Cadeaux, 3 Vêtements, 2 Bébé & Enfant, 1 Auto & Moto.

The same code should not be written for one shop several times with different description. One promo code should be written one time for one shop. Then, with these fields, you need to create and fill an JSON code. Answer with only generated JSON code and nothing more. Do not include any explanation or reply introductions. Answer must not contain code blocks ("```json" and "```"). If no action or promo code found, answer with a space symbol ( ).

The JSON should have ONLY these fields below and double-check its validity. All comments are additional instructions for you, remove it from the answer. Appear found fields to corresponding fields in square brackets:

If the E-mail does not contain any presence of action or promo code, do not send json. Instead, send only space symbol. Never compose information which is not present in the e-mail: no codes, no dates or discounts should be written that are not in the e-mail.

[
  {
    "shop": "(shop)",
    "domain": "(domain)",
    "description": "(descr)",
    "full_description": "(full_descr)",
    "code": "(promo code)",
    "date_start": "(date_start)",
    "date_end": "(date_end)",
    "offer_type": "(offer_type)",
    "target_url": "(target_url)",
    "click_url": "(click_url)",
    "discount": "(discount)",
    "categories": ["(category_id)"]
  }
]

Double-check that every parameter from example is present in result (shop, domain, description, full_description, code, date_start, date_end, categories). Also check that date_start and date_end are in the following format: Y-M-D Hr:Min

Domain to use in "domain" field: {domain}

E-mail: [EMAIL]
"""
