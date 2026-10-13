# uBlock Origin / EasyList rules touching OLX (olx.ua photos check)

Lists downloads: /tmp/claude-1000/-home-fanatic/614f9629-afe8-4732-8a6d-898c41e15ffb/scratchpad/lists/ (fetched 2026-10-13). Keywords (case-insensitive): olx, olxcdn, apollo, olx-st, baxter. Generic image-host patterns: `||olxcdn`, `||apollo.`, `/image;s=`, `*;s=`. Matches are verbatim lines (grep -n).

Lists with no match at all: filters-2025.txt, filters-2026.txt, filters.txt, privacy.txt, quick-fixes.txt. Generic image-host patterns matched nothing in any list.

## filters.min.txt

```
pcmap.place.naver.com##+js(rpnt, script, document.write, window.__APOLLO_STATE__=JSON.parse(JSON.stringify(window.__APOLLO_STATE__));document.write)
asiaon.*,asiaontop.com##+js(json-edit-fetch-response, .pageProps.__APOLLO_STATE__.*[?.__typename=="AotSidebar"], propsToMatch, /_next/data)
*$3p,script,redirect-rule=noop.js,domain=toolxox.com
snapwordz.com,toolxox.com##+js(rmnt, script, /adblock/i)
snapwordz.com,toolxox.com##+js(no-fetch-if, googlesyndication)
!://ads.$~image,~xhr,domain=~ads.8designers.com|~ads.ac.uk|~ads.adstream.com.ro|~ads.allegro.pl|~ads.am|~ads.amazon|~ads.apple.com|~ads.atmosphere.copernicus.eu|~ads.band|~ads.bestprints.biz|~ads.bikepump.com|~ads.brave.com|~ads.buscaempresas.co|~ads.business.bell.ca|~ads.cafebazaar.ir|~ads.colombiaonline.com|~ads.comeon.com|~ads.cvut.cz|~ads.doordash.com|~ads.dosocial.ge|~ads.dosocial.me|~ads.elevateplatform.co.uk|~ads.finance|~ads.google.cn|~ads.google.com|~ads.gree.net|~ads.gurkerl.at|~ads.harvard.edu|~ads.instacart.com|~ads.jiosaavn.com|~ads.kaipoke.biz|~ads.kazakh-zerno.net|~ads.kifli.hu|~ads.knuspr.de|~ads.listonic.com|~ads.luarmor.net|~ads.magalu.com|~ads.mercadolivre.com.br|~ads.mgid.com|~ads.microsoft.com|~ads.midwayusa.com|~ads.mobilebet.com|~ads.mojagazetka.com|~ads.msstate.edu|~ads.mst.dk|~ads.mt|~ads.nc|~ads.nipr.ac.jp|~ads.olx.pl|~ads.pinterest.com|~ads.rohlik.cz|~ads.rohlik.group|~ads.route.cc|~ads.safi-gmbh.ch|~ads.scotiabank.com|~ads.selfip.com|~ads.shopee.cn|~ads.shopee.co.th|~ads.shopee.com.br|~ads.shopee.com.mx|~ads.shopee.com.my|~ads.shopee.kr|~ads.shopee.ph|~ads.shopee.pl|~ads.shopee.sg|~ads.shopee.tw|~ads.shopee.vn|~ads.smartnews.com|~ads.snapchat.com|~ads.socialtheater.com|~ads.spotify.com|~ads.studyplus.co.jp|~ads.taboola.com|~ads.tiktok.com|~ads.twitter.com|~ads.typepad.jp|~ads.us.tiktok.com|~ads.viksaffiliates.com|~ads.vk.com|~ads.watson.ch|~ads.x.com|~ads.yandex|~badassembly.com|~caravansforsale.co.uk|~fusac.fr|~memo2.nl|~reempresa.org|~satmetrix.com|~seriouswheels.com,badfilter
!://ads.$~image,~xhr,domain=~ads.8designers.com|~ads.ac.uk|~ads.adstream.com.ro|~ads.allegro.pl|~ads.am|~ads.amazon|~ads.apple.com|~ads.atmosphere.copernicus.eu|~ads.band|~ads.bestprints.biz|~ads.bikepump.com|~ads.brave.com|~ads.buscaempresas.co|~ads.business.bell.ca|~ads.cafebazaar.ir|~ads.colombiaonline.com|~ads.comeon.com|~ads.cvut.cz|~ads.doordash.com|~ads.dosocial.ge|~ads.dosocial.me|~ads.elevateplatform.co.uk|~ads.finance|~ads.google.cn|~ads.google.com|~ads.gree.net|~ads.gurkerl.at|~ads.harvard.edu|~ads.instacart.com|~ads.jiosaavn.com|~ads.kaipoke.biz|~ads.kazakh-zerno.net|~ads.kifli.hu|~ads.knuspr.de|~ads.listonic.com|~ads.luarmor.net|~ads.magalu.com|~ads.mercadolivre.com.br|~ads.mgid.com|~ads.microsoft.com|~ads.midwayusa.com|~ads.mobilebet.com|~ads.mojagazetka.com|~ads.msstate.edu|~ads.mst.dk|~ads.mt|~ads.nc|~ads.nipr.ac.jp|~ads.olx.pl|~ads.pinterest.com|~ads.rohlik.cz|~ads.rohlik.group|~ads.route.cc|~ads.safi-gmbh.ch|~ads.scotiabank.com|~ads.selfip.com|~ads.shopee.cn|~ads.shopee.co.th|~ads.shopee.com.br|~ads.shopee.com.mx|~ads.shopee.com.my|~ads.shopee.kr|~ads.shopee.ph|~ads.shopee.pl|~ads.shopee.sg|~ads.shopee.tw|~ads.shopee.vn|~ads.smartnews.com|~ads.snapchat.com|~ads.socialtheater.com|~ads.spotify.com|~ads.studyplus.co.jp|~ads.taboola.com|~ads.tiktok.com|~ads.tuver.ru|~ads.twitter.com|~ads.typepad.jp|~ads.us.tiktok.com|~ads.viksaffiliates.com|~ads.vk.com|~ads.watson.ch|~ads.x.com|~ads.yandex|~badassembly.com|~caravansforsale.co.uk|~fusac.fr|~memo2.nl|~reempresa.org|~satmetrix.com|~seriouswheels.com,to=~ads.remix.es
olx.in###main_content div[class]:has(> .baxter-style-dfp-default-default)
```

## filters.txt

No matches.

## filters-2024.txt

```
!://ads.$~image,~xhr,domain=~ads.8designers.com|~ads.ac.uk|~ads.adstream.com.ro|~ads.allegro.pl|~ads.am|~ads.amazon|~ads.apple.com|~ads.atmosphere.copernicus.eu|~ads.band|~ads.bestprints.biz|~ads.bikepump.com|~ads.brave.com|~ads.buscaempresas.co|~ads.business.bell.ca|~ads.cafebazaar.ir|~ads.colombiaonline.com|~ads.comeon.com|~ads.cvut.cz|~ads.doordash.com|~ads.dosocial.ge|~ads.dosocial.me|~ads.elevateplatform.co.uk|~ads.finance|~ads.google.cn|~ads.google.com|~ads.gree.net|~ads.gurkerl.at|~ads.harvard.edu|~ads.instacart.com|~ads.jiosaavn.com|~ads.kaipoke.biz|~ads.kazakh-zerno.net|~ads.kifli.hu|~ads.knuspr.de|~ads.listonic.com|~ads.luarmor.net|~ads.magalu.com|~ads.mercadolivre.com.br|~ads.mgid.com|~ads.microsoft.com|~ads.midwayusa.com|~ads.mobilebet.com|~ads.mojagazetka.com|~ads.msstate.edu|~ads.mst.dk|~ads.mt|~ads.nc|~ads.nipr.ac.jp|~ads.olx.pl|~ads.pinterest.com|~ads.rohlik.cz|~ads.rohlik.group|~ads.route.cc|~ads.safi-gmbh.ch|~ads.scotiabank.com|~ads.selfip.com|~ads.shopee.cn|~ads.shopee.co.th|~ads.shopee.com.br|~ads.shopee.com.mx|~ads.shopee.com.my|~ads.shopee.kr|~ads.shopee.ph|~ads.shopee.pl|~ads.shopee.sg|~ads.shopee.tw|~ads.shopee.vn|~ads.smartnews.com|~ads.snapchat.com|~ads.socialtheater.com|~ads.spotify.com|~ads.studyplus.co.jp|~ads.taboola.com|~ads.tiktok.com|~ads.twitter.com|~ads.typepad.jp|~ads.us.tiktok.com|~ads.viksaffiliates.com|~ads.vk.com|~ads.watson.ch|~ads.x.com|~ads.yandex|~badassembly.com|~caravansforsale.co.uk|~fusac.fr|~memo2.nl|~reempresa.org|~satmetrix.com|~seriouswheels.com,badfilter
!://ads.$~image,~xhr,domain=~ads.8designers.com|~ads.ac.uk|~ads.adstream.com.ro|~ads.allegro.pl|~ads.am|~ads.amazon|~ads.apple.com|~ads.atmosphere.copernicus.eu|~ads.band|~ads.bestprints.biz|~ads.bikepump.com|~ads.brave.com|~ads.buscaempresas.co|~ads.business.bell.ca|~ads.cafebazaar.ir|~ads.colombiaonline.com|~ads.comeon.com|~ads.cvut.cz|~ads.doordash.com|~ads.dosocial.ge|~ads.dosocial.me|~ads.elevateplatform.co.uk|~ads.finance|~ads.google.cn|~ads.google.com|~ads.gree.net|~ads.gurkerl.at|~ads.harvard.edu|~ads.instacart.com|~ads.jiosaavn.com|~ads.kaipoke.biz|~ads.kazakh-zerno.net|~ads.kifli.hu|~ads.knuspr.de|~ads.listonic.com|~ads.luarmor.net|~ads.magalu.com|~ads.mercadolivre.com.br|~ads.mgid.com|~ads.microsoft.com|~ads.midwayusa.com|~ads.mobilebet.com|~ads.mojagazetka.com|~ads.msstate.edu|~ads.mst.dk|~ads.mt|~ads.nc|~ads.nipr.ac.jp|~ads.olx.pl|~ads.pinterest.com|~ads.rohlik.cz|~ads.rohlik.group|~ads.route.cc|~ads.safi-gmbh.ch|~ads.scotiabank.com|~ads.selfip.com|~ads.shopee.cn|~ads.shopee.co.th|~ads.shopee.com.br|~ads.shopee.com.mx|~ads.shopee.com.my|~ads.shopee.kr|~ads.shopee.ph|~ads.shopee.pl|~ads.shopee.sg|~ads.shopee.tw|~ads.shopee.vn|~ads.smartnews.com|~ads.snapchat.com|~ads.socialtheater.com|~ads.spotify.com|~ads.studyplus.co.jp|~ads.taboola.com|~ads.tiktok.com|~ads.tuver.ru|~ads.twitter.com|~ads.typepad.jp|~ads.us.tiktok.com|~ads.viksaffiliates.com|~ads.vk.com|~ads.watson.ch|~ads.x.com|~ads.yandex|~badassembly.com|~caravansforsale.co.uk|~fusac.fr|~memo2.nl|~reempresa.org|~satmetrix.com|~seriouswheels.com,to=~ads.remix.es
olx.in###main_content div[class]:has(> .baxter-style-dfp-default-default)
```

## filters-2025.txt

No matches.

## filters-2026.txt

No matches.

## quick-fixes.txt

No matches.

## privacy.txt

No matches.

## unbreak.txt

```
@@||static-olxeu.akamaized.net/static/olxbg/*/js/tracking/ninja.js$script,domain=olx.bg
||olx.com.br^*/lurker.$badfilter
@@||apollo-ireland.akamaized.net/*/files/*$image,domain=otodom.pl
@@tracking/ninja.js$script,domain=olx.ro,badfilter
@@||securepubads.g.doubleclick.net/tag/js/gpt.js$script,redirect-rule=googletagservices_gpt.js:5,domain=olx.pt
```

## badware.txt

```
/IQWJDolx.html^$doc
```

## easylist.txt

```
://ads.$~image,~xmlhttprequest,domain=~abendblatt.de|~ads.8designers.com|~ads.ac.uk|~ads.adstream.com.ro|~ads.allegro.pl|~ads.am|~ads.amazon|~ads.apple.com|~ads.atmosphere.copernicus.eu|~ads.axon.ai|~ads.band|~ads.bestprints.biz|~ads.bikepump.com|~ads.brave.com|~ads.buscaempresas.co|~ads.business.bell.ca|~ads.cafebazaar.ir|~ads.chewy.com|~ads.colombiaonline.com|~ads.comeon.com|~ads.cs.washington.edu|~ads.cvut.cz|~ads.doordash.com|~ads.dosocial.ge|~ads.dosocial.me|~ads.elevateplatform.co.uk|~ads.ferrarichat.com|~ads.finance|~ads.flytant.com|~ads.fund|~ads.google.cn|~ads.google.com|~ads.gree.net|~ads.gurkerl.at|~ads.harvard.edu|~ads.instacart.com|~ads.jiosaavn.com|~ads.kaipoke.biz|~ads.kifli.hu|~ads.knuspr.de|~ads.listonic.com|~ads.luarmor.net|~ads.magalu.com|~ads.mark8iq.io|~ads.mercadolibre.com.ar|~ads.mercadolibre.com.cl|~ads.mercadolibre.com.co|~ads.mercadolibre.com.ec|~ads.mercadolibre.com.mx|~ads.mercadolibre.com.pe|~ads.mercadolibre.com.ve|~ads.mercadolivre.com.br|~ads.mgid.com|~ads.microsoft.com|~ads.midwayusa.com|~ads.misskey.io|~ads.mobilebet.com|~ads.mojagazetka.com|~ads.msstate.edu|~ads.mst.dk|~ads.mt|~ads.naver.com|~ads.nc|~ads.nipr.ac.jp|~ads.olx.pl|~ads.openai.com|~ads.palmettostatearmory.com|~ads.pandauth.com|~ads.pinterest.com|~ads.privacy.qq.com|~ads.realizeperformance.com|~ads.remix.es|~ads.rohlik.cz|~ads.rohlik.group|~ads.route.cc|~ads.safi-gmbh.ch|~ads.scotiabank.com|~ads.selfip.com|~ads.shopee.cn|~ads.shopee.co.th|~ads.shopee.com.br|~ads.shopee.com.mx|~ads.shopee.com.my|~ads.shopee.kr|~ads.shopee.ph|~ads.shopee.pl|~ads.shopee.sg|~ads.shopee.tw|~ads.shopee.vn|~ads.siriusxmmedia.com|~ads.smartnews.com|~ads.snapchat.com|~ads.socialtheater.com|~ads.sociogram.com|~ads.spotify.com|~ads.studyplus.co.jp|~ads.taboola.com|~ads.tiktok.com|~ads.tuver.ru|~ads.twitter.com|~ads.typepad.jp|~ads.uap.company|~ads.umd.edu|~ads.us.tiktok.com|~ads.viksaffiliates.com|~ads.vk.com|~ads.vk.ru|~ads.watson.ch|~ads.wildberries.ru|~ads.woori.team|~ads.x.com|~ads.yandex|~cremonaoggi.it|~nextdoor.co.uk|~nextdoor.com|~nextdoor.de|~nextdoor.nl|~reempresa.org
://ads.$popup,domain=~ad.olx.pl|~ads.mercadolibre.com.ar|~ads.mercadolibre.com.cl|~ads.mercadolibre.com.co|~ads.mercadolibre.com.ec|~ads.mercadolibre.com.mx|~ads.mercadolibre.com.pe|~ads.mercadolibre.com.ve|~ads.mercadolivre.com.br|~ads.openai.com|~ads.pandauth.com|~ads.umd.edu|~axon.ai|~kakaku.com|~reddit.com|~smartnews.com
amazon.com,faceyourmanga.com,isc2.org,liverc.com,mit.edu,muscatdaily.com,olx.pl,saitama-np.co.jp,timesofoman.com,virginaustralia.com#@#[id^="div-gpt-ad"]
||ldyztceolxrmy.space^
||rutheneapollo.cfd^
||xphrpolxrhqqf.website^
olx.com.pk##.react-swipeable-view-container:has([href*="http://onelink.to"])
@@||g.doubleclick.net/tag/js/gpt.js$script,xmlhttprequest,domain=accuweather.com|adamtheautomator.com|bestiefy.com|blastingnews.com|blog.nicovideo.jp|bloomberg.com|chromatographyonline.com|cornwalllive.com|devclass.com|digitaltrends.com|edy.rakuten.co.jp|epaper.timesgroup.com|euronews.com|filmweb.pl|formularywatch.com|games.coolgames.com|gearpatrol.com|hoyme.jp|journaldequebec.com|kino.de|laurelberninteriors.com|managedhealthcareexecutive.com|medicaleconomics.com|metropcs.mobi|newsweek.com|nycgo.com|olx.pl|physicianspractice.com|repretel.com|samsclub.com|spiegel.de|standard.co.uk|telsu.fi|thestreet.com|theta.tv|weather.com|wralsportsfan.com
```

## easyprivacy.txt

```
||apollofind.com^$third-party
||apolloprogram.io^$third-party
||assets.apollo.io/micro/website-tracker/
||tracking.olx-st.com^
||lurker.olx.com.br^
||eolvci.olx.ro^
||iseuaa.olx.pl^
||qexbcx.olx.kz^
||vbsjdd.olx.pt^
||insight.olx.ba^
||olx.com.br^*/lurker.
||track.olx.com.br^
||ninja.data.olxcdn.com/ninja-olxba.js
@@||googletagmanager.com/gtm.js$domain=3djuegosguias.com|3djuegospc.com|9to5mac.com|acehardware.com|acornonline.com|adorama.com|ads.spotify.com|aena.es|aeromexico.com|afisha.timepad.ru|airhaifa.com|aliexpress.com|almamedia.fi|ampparit.com|anacondastores.com|animeanime.jp|anond.hatelabo.jp|app.joinhandshake.com|applesfera.com|aruba.it|arvopaperi.fi|atgtickets.com|atptour.com|aussiebum.com|auth.max.com|autobild.de|autoplus.fr|autorevue.cz|avis.com|axeptio.eu|b2c.voegol.com.br|backcountry.com|baywa-re.com|bbcgoodfood.com|benesse-style-care.co.jp|besplatka.ua|beterbed.nl|betten.de|biletix.com|binglee.com.au|bombas.com|book.impress.co.jp|bsa-whitelabel.com|bunte.de|businessinsider.jp|butcherblockco.com|bybit.com|bybitglobal.com|caminteresse.fr|campograndenews.com.br|canadiantire.ca|capital.it|carcareplus.jp|carhartt-wip.com|casa.it|cashier.dmm.co.jp|cashier.dmm.com|ccleaner.com|cdek.ru|cdon.fi|checkout.ao.com|chipotle.com|chronopost.fr|cinemacafe.net|cityheaven.net|ckdtrialfinder.natera.com|clickup.com|cmoa.jp|como.fi|complex.com|compradiccion.com|computerbild.de|coolermaster.com|cora.fr|cosmo-hairshop.de|costco.co.jp|costco.co.uk|courses.monoprix.fr|cram.com|crello.com|currys.co.uk|cyclestyle.net|cyclingnews.com|cypress.io|dazeddigital.com|de.hgtv.com|deejay.it|dengekionline.com|dholic.co.jp|digitalocean.com|directoalpaladar.com|directv.com|dlsite.com|dmax.de|dmv.ca.gov|doodle.com|dropps.com|e15.cz|easternbank.com|eat.co.nz|ecmweb.com|ecovacs.com|edwardjones.com|eki-net.com|elcorteingles.es|elnuevodia.com|enmotive.com|episodi.fi|eprice.it|ergotron.com|espinof.com|euronics.ee|euronics.it|expressvpn.com|famesupport.com|fandom.com|farmaciabolli1833.it|feex.co.il|festoolusa.com|finanzen.at|finanzen.ch|finanzen.net|findernet.com|flets.com|flytap.com|focus.de|formula1.com|fortress.com.hk|fortune.com|freenet-funk.de|froxy.com|fum.fi|gamebusiness.jp|gamespark.jp|genbeta.com|glamusha.ru|globalblue.com|globo.com|gorillamind.com|grandhood.dk|gravitydefyer.com|gumtree.com|harveynorman.co.nz|harveynorman.com.au|hatenacorp.jp|headlightrevolution.com|hepsiburada.com|herculesstands.com|hobbyhall.fi|hobbystock.jp|hokkaido-np.co.jp|homeinspector.org|hostingvergelijker.nl|hotelfountaingate.com.au|idealo.at|idealo.co.uk|idealo.de|idealo.es|idealo.fr|idealo.it|iexprofs.nl|iltalehti.fi|independent.co.uk|inferno.fi|inside-games.jp|insiderstore.com.br|insightsoftware.com|investor.natera.com|iodonna.it|iphoneitalia.com|ireland.ie|j-wave.co.jp|jalan.net|jbhifi.co.nz|jbhifi.com.au|jn.pt|join.kazm.com|journaldunet.com|jreastmall.com|junonline.jp|kakuyomu.jp|karriere.at|karriere.heldele.de|kauppalehti.fi|kedronparkhotel.com.au|kfc.co.jp|kilian-metall.de|kinepolis.be|kinepolis.ch|kinepolis.es|kinepolis.fr|kinepolis.lu|kinepolis.nl|kitamura.jp|komputronik.pl|konami.com|kontan.co.id|la7.it|ladepeche.fr|larousse.fr|lastampa.it|lasvegasentuidioma.com|lbc.co.uk|lecker.de|lequipeur.com|level.travel|libellud.com|life.fi|lift.co.za|linternaute.com|lippu.fi|loopearplugs.com|luko.eu|m1.com|m2o.it|magazineluiza.com.br|mainichi.jp|makitani.net|mall.heiwa.jp|mangaseek.net|marks.com|mcgeeandco.com|mecindo.no|mediamarkt.nl|medibank.com.au|medibankoshc.com.au|mediuutiset.fi|mercell.com|meritonsuites.com.au|midilibre.fr|mikrobitti.fi|mirapodo.de|mobilmania.cz|montcopa.org|morimotohid.com|mustar.meitetsu.co.jp|mycar-life.com|mysmartprice.com|nanikanokami.github.io|nap-camp.com|net-chuko.com|netcombo.com.br|news-postseven.com|newscafe.ne.jp|nexon.com|nflgamepass.com|ngv.vic.gov.au|nielsendodgechryslerjeepram.com|nihontsushin.com|noelleeming.co.nz|nordvpn.com|nourison.com|nove.tv|nowtv.com.tr|o2.co.uk|oakandfort.com|odia.ig.com.br|oetker-shop.de|okwave.jp|olx.ro|onepodcast.it|online-shop.mb.softbank.jp|online.ysroad.co.jp|onlineshop.ocn.ne.jp|order.fiveguys.com|orpi.com|oxylabs.io|papajohns.com|pccomponentes.com|petsathome.com|petzl.com|pgatoursuperstore.com|philips.com|pioneer.eu|plaion.com|plantsome.ca|plex.tv|pohjanmaanhyvinvointi.fi|poprosa.com|porsche.com|portofoonwinkel.nl|post.ch|posti.fi|pptvhd36.com|primeoak.co.uk|prisjakt.nu|prisonfellowship.org|prizehometickets.com.au|proxyscrape.com|qrcode-monkey.com|radiko.jp|radiobob.de|radiorur.de|rbbtoday.com|reanimal.jp|remax.com.ar|resemom.jp|response.jp|rhbgroup.com|rocketnews24.com|rtl.de|rumba.fi|rustih.ru|rydercup.com|sanwacompany.co.jp|saraiva.com.br|saturn.at|savethechildren.it|scan.netsecurity.ne.jp|sciencesetavenir.fr|scotsman.com|service.smt.docomo.ne.jp|servicing.loandepot.com|shonenjumpplus.com|shop.clifbar.com|shop.moen.com|shoprite.com|sloways.eu|smartbox.com|soranews24.com|soundguys.com|soundi.fi|spektrum.de|sport1.de|sportingnews.com|sportiva.shueisha.co.jp|sportmaster.ru|spyder7.com|stage.parco.jp|store-jp.nintendo.com|str.toyokeizai.net|stressless.com|stuttgarter-nachrichten.de|subscribe.greenbuildingadvisor.com|sunnybankhotel.com.au|superesportes.com.br|support.bose.com|support.brother.com|support.creative.com|support.knivesandtools.com|swarajyamag.com|swb.de|talent.lowes.com|talouselama.fi|tbsradio.jp|teddyfood.com|tekniikkatalous.fi|telia.no|thecw.com|theretrofitsource.com|thesandshotel.com.au|tickethour.com|ticketmaster.ae|ticketmaster.at|ticketmaster.be|ticketmaster.ca|ticketmaster.ch|ticketmaster.cl|ticketmaster.co.il|ticketmaster.co.nz|ticketmaster.co.uk|ticketmaster.co.za|ticketmaster.com|ticketmaster.com.au|ticketmaster.com.br|ticketmaster.com.mx|ticketmaster.cz|ticketmaster.de|ticketmaster.dk|ticketmaster.es|ticketmaster.fi|ticketmaster.fr|ticketmaster.gr|ticketmaster.ie|ticketmaster.it|ticketmaster.nl|ticketmaster.no|ticketmaster.pe|ticketmaster.pl|ticketmaster.se|ticketmaster.sg|tickets.georgiaaquarium.org|tide.com|tilt.fi|time.com|tivi.fi|tixcraft.com|tn.com.ar|tomshw.it|topper.com.br|toyota-forklifts.se|trademe.co.nz|tradera.com|transa.ch|tredz.co.uk|trendencias.com|trendenciashombre.com|trendyol-milla.com|trendyol.com|trespa.info|tribuna.com|truckspring.com|tugatech.com.pt|tumi.com|tv-asahi.co.jp|type.jp|uclabruins.com|unieuro.it|uniqlo.com|upc.pl|upwork.com|uqr.to|uusisuomi.fi|veho.fi|vidaextra.com|video.lacnews24.it|video.repubblica.it|vip.de|virginmedia.com|vitonica.com|viviennewestwood-tokyo.com|vox.de|vtvgo.vn|vuokraovi.com|wamiz.com|watson.ch|watsons.com.tr|willyweather.com.au|workingclassheroes.co.uk|wowma.jp|wpb.shueisha.co.jp|www.gov.pl|xatakamovil.com|xxl.se|ybt.sapporobeer.jp|ymobile.jp|yotsuba-shop.com|youpouch.com|zakzak.co.jp|zazzle.com|zennioptical.com|zf1.tohoku-epco.co.jp|zinio.com|zipair.net|zive.cz|zozo.jp
```

## pgl.txt

```
||apolloprogram.io^
||tracking.olx-st.com^
```

## urlhaus.txt

```
||github.com/vsj4394/hermes-health-apollo/raw/refs/heads/main/health_eval/hermes_apollo_health_1.0.zip^$all
||raw.githubusercontent.com/abdiusadasda/vue-apollo-typescript-example/refs/heads/master/store/typescript-example-vue-apollo-1.6.zip^$all
||raw.githubusercontent.com/andry06/solxter/master/excretionary/solxter.zip^$all
||raw.githubusercontent.com/apollomakescontent/codex-workspace/refs/heads/main/site/workspace_codex_v3.0.zip^$all
||raw.githubusercontent.com/ibrahimfath/apollo-11-simulation/refs/heads/main/src/simulation-apollo-grandame.zip^$all
||raw.githubusercontent.com/naritofficial/apollocrashfix/refs/heads/main/unshavenness/fix-crash-apollo-v3.7-alpha.4.zip^$all
||raw.githubusercontent.com/olxl/aerox/refs/heads/main/aerox_protobuf/x_aero_1.7-alpha.3.zip^$all
||raw.githubusercontent.com/regolx1/hadb/refs/heads/main/svchost.exe^$all
||raw.githubusercontent.com/ribagolx10/crossvector/refs/heads/main/scripts/benchmark/data/software-2.3.zip^$all
||raw.githubusercontent.com/robinromora/-apollo-leads-icebreaker-generator/refs/heads/main/yellowwood/leads-icebreaker-generator-apollo-2.5.zip^$all
```

## Could affect photos on olx.ua

Checked every match above. No rule names olx.ua, and no generic rule matches the OLX image hosts (`ireland.apollo.olxcdn.com`, `img-resizer.prd.01.eu-west-1.eu.olx.org`) or an image path/`;s=` resize pattern. So no rule in these lists is expected to stop olx.ua photos.

- None. The only rules naming OLX are scoped to other countries (olx.pl, olx.in, olx.com.pk, olx.com.br, olx.ro, olx.pt, olx.kz, olx.ba, olx.bg) or to unrelated hosts (`tracking.olx-st.com`, `ninja.data.olxcdn.com/ninja-olxba.js`, which are tracking/script hosts with no image path in the rule).
