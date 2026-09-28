"""Printing a typed form back out as a UPSC DAF-I.

An aspirant who types their details here should be able to walk away with the
same document they would have downloaded from the Commission — same eight
pages, same numbering, same wording, same two-column label/value layout with
the ``|`` gutter, same Times face, same footer on every page.

The reference is a real submitted form: PREETAM_KUMAR_DAF_1_compressed.pdf,
Civil Services (Main) Examination, 2021. Everything printed here that is not
the candidate's own data is the Commission's own boilerplate, transcribed from
it verbatim — the notes under Community, the four scribe notes, the fee text,
the declaration.

Our form asks about thirty-five things; DAF-I has closer to two hundred fields.
Anything we never asked for is left blank after its ``|``, which is exactly
what the real form does with a question the candidate did not answer. Nothing
is invented to fill a gap.
"""

from __future__ import annotations

import io
from typing import Iterable, Sequence

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4

# The real form runs almost edge to edge — its footer rule spans the sheet and
# the education table is wider than a normal text block. A conventional 1-inch
# margin would not fit it.
LEFT = 14.0
RIGHT = PAGE_W - 14.0
WIDTH = RIGHT - LEFT

# Where the value column's separator sits. Every labelled row on every page
# lines up on it, which is most of what makes the form recognisable.
GUTTER_X = 234.0
VALUE_X = GUTTER_X + 7.0

BODY = "Times-Roman"
BOLD = "Times-Bold"
SIZE = 11.0
# Measured off the reference: its rows sit on a 31px pitch at 150dpi. Getting
# this wrong by half a point is the difference between eight pages and ten.
LEADING = 14.88

TOP_Y = PAGE_H - 44.0
# Above the footer rule. Content that would cross it takes a new page.
FLOOR_Y = 62.0

TOTAL_PAGES = 8


class Sheet:
    """A canvas with a cursor, the form's header and footer, and one column.

    Deliberately small. The layout is fixed by the reference document, so the
    pages below place their own content and only lean on this for the parts
    that repeat.
    """

    def __init__(self, roll_no: str = "") -> None:
        self.buffer = io.BytesIO()
        self.c = canvas.Canvas(self.buffer, pagesize=A4)
        self.c.setTitle("Detailed Application Form (DAF-I)")
        self.roll_no = roll_no
        self.page = 1
        self.y = TOP_Y
        self._chrome()

    # --- page furniture ---

    def _chrome(self) -> None:
        """"Page No. n/8" at the top, the roll-number band at the foot."""
        self.c.setFont(BODY, SIZE)
        self.c.drawRightString(RIGHT - 6, PAGE_H - 22, f"Page No. {self.page}/{TOTAL_PAGES}")

        self.c.setLineWidth(0.7)
        self.c.line(LEFT - 4, 50, RIGHT + 4, 50)
        self.c.rect(LEFT - 4, 12, WIDTH + 8, 30, stroke=1, fill=0)
        self.c.setFont(BOLD, SIZE)
        self.c.drawString(LEFT, 22, "Roll No. :-")
        self.c.setFont(BODY, SIZE)
        self.c.drawString(LEFT + 62, 22, self.roll_no.upper())
        self.c.drawString(LEFT + 200, 22, "|")
        # The candidate's signature block, present on every page of the real
        # form. Left as an empty box: we are not going to draw a signature.
        self.c.rect(RIGHT - 122, 12, 122, 30, stroke=1, fill=0)

    def new_page(self) -> None:
        self.c.showPage()
        self.page += 1
        self.y = TOP_Y
        self._chrome()

    def space(self, points: float = LEADING) -> None:
        self.y -= points

    def _room(self, needed: float) -> None:
        if self.y - needed < FLOOR_Y:
            self.new_page()

    # --- primitives ---

    def text(self, x: float, s: str, *, bold: bool = False, size: float = SIZE) -> None:
        self.c.setFont(BOLD if bold else BODY, size)
        self.c.drawString(x, self.y, s)

    def wrap(self, s: str, width: float, *, bold: bool = False, size: float = SIZE) -> list[str]:
        font = BOLD if bold else BODY
        lines: list[str] = []
        line = ""

        for word in s.split():
            trial = f"{line} {word}".strip()
            if stringWidth(trial, font, size) <= width:
                line = trial
                continue
            if line:
                lines.append(line)
                line = ""
            # A word wider than its column is broken mid-word rather than
            # allowed to run over the rule — which is what the reference does
            # in the narrow table headings ("recomm/ended", "appoi/nted").
            while stringWidth(word, font, size) > width:
                cut = len(word)
                while cut > 1 and stringWidth(word[:cut], font, size) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word

        if line:
            lines.append(line)
        return lines

    def row(
        self,
        label: str | Sequence[str],
        value: str = "",
        *,
        x: float = LEFT,
        gutter: bool = True,
        value_on: int = -1,
        bold_value: bool = True,
    ) -> None:
        """One labelled row: label at the left, ``|`` at the gutter, value after.

        ``value_on`` picks which line of a multi-line label the value sits
        beside — the real form aligns it with the last line, which is what -1
        gives, but several entries align it with the first.
        """
        lines = [label] if isinstance(label, str) else list(label)
        self._room(LEADING * len(lines))
        target = value_on if value_on >= 0 else len(lines) - 1

        for i, line in enumerate(lines):
            self.text(x, line)
            if gutter and i == target:
                self.text(GUTTER_X, "|")
                if value:
                    self.text(VALUE_X, value, bold=bold_value)
            self.y -= LEADING

    def para(
        self,
        s: str,
        *,
        x: float = LEFT,
        indent: float = 0.0,
        width: float | None = None,
        bold: bool = False,
        size: float = SIZE,
        leading: float | None = None,
    ) -> None:
        """Full-width prose with a hanging indent, as the notes are set."""
        lead = leading or LEADING
        avail = width if width is not None else (RIGHT - x)
        lines = self.wrap(s, avail, bold=bold, size=size)
        self._room(lead * len(lines))
        for i, line in enumerate(lines):
            self.text(x + (indent if i else 0), line, bold=bold, size=size)
            self.y -= lead

    def centre(self, s: str, *, bold: bool = True, size: float = 14.0) -> None:
        self.c.setFont(BOLD if bold else BODY, size)
        self.c.drawCentredString(PAGE_W / 2, self.y, s)
        self.y -= size + 4

    def grid(
        self,
        widths: Sequence[float],
        rows: Iterable[Sequence[str]],
        *,
        x: float = LEFT,
        bold_rows: Sequence[int] = (),
        centre_cols: Sequence[int] | None = None,
        size: float = SIZE - 1,
    ) -> None:
        """A ruled table. Cells wrap and every cell in a row shares its height."""
        lead = size + 3
        centred = set(range(len(widths)) if centre_cols is None else centre_cols)

        for r, cells in enumerate(rows):
            bold = r in bold_rows
            wrapped = [
                self.wrap(str(cell), w - 8, bold=bold, size=size) or [""]
                for cell, w in zip(cells, widths)
            ]
            height = max(len(w) for w in wrapped) * lead + 4
            self._room(height)

            top = self.y + size
            cx = x
            for col, (lines, w) in enumerate(zip(wrapped, widths)):
                self.c.rect(cx, top - height, w, height, stroke=1, fill=0)
                ty = top - lead
                for line in lines:
                    self.c.setFont(BOLD if bold else BODY, size)
                    if col in centred:
                        self.c.drawCentredString(cx + w / 2, ty, line)
                    else:
                        self.c.drawString(cx + 4, ty, line)
                    ty -= lead
                cx += w
            self.y = top - height - size

    def done(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buffer.getvalue()


def _v(form: dict, key: str, default: str = "") -> str:
    """A value as the form prints it — upper case, or blank if never given."""
    return str(form.get(key) or default).strip().upper()


def _first(form: dict, key: str) -> str:
    """The first item of a comma-separated field, e.g. the top service."""
    raw = str(form.get(key) or "")
    return raw.split(",")[0].strip().upper()


# Column widths, in points, taken off the reference form.
EDU_COLS = (88.8, 42.2, 55.2, 28.8, 32.2, 38.4, 93.6, 103.2, 86.4)
APPLIED_COLS = (167.0, 57.6, 51.4, 54.2, 53.8, 55.2, 40.8, 88.8)
PWBD_COLS = (328.8, 108.0, 110.4)


def build_daf_pdf(form: dict, *, email: str = "", phone: str = "", year: str = "2021") -> bytes:
    """Render a typed form as DAF-I. Returns the PDF bytes."""
    roll = _v(form, "roll_number")
    s = Sheet(roll_no=roll)

    _page1(s, form, email, phone, year)
    s.new_page()
    _page2(s, form, year)
    s.new_page()
    _page3(s, form, year)
    s.new_page()
    _page4(s, form)
    s.new_page()
    _page5(s, form)
    s.new_page()
    _page6(s, form, year)
    s.new_page()
    _page7(s, form, year)
    s.new_page()
    _page8(s, form, year)

    return s.done()


def _page1(s: Sheet, f: dict, email: str, phone: str, year: str) -> None:
    # Absolute positions, all measured off the reference sheet: the title
    # block, the identity block, the photo box and the rule under it are fixed
    # furniture, and the first numbered field must land at y=573.
    s.y = 808
    s.centre("UNION PUBLIC SERVICE COMMISSION")
    s.centre("DETAILED APPLICATION FORM [DAF]-I")
    s.centre(f"CIVIL SERVICES (MAIN) EXAMINATION, {year}")

    s.y = 733
    for label, value in (
        ("RID. :", _v(f, "rid")),
        ("Roll No. :", _v(f, "roll_number")),
        ("Name :", _v(f, "full_name")),
        ("Email :", email.upper()),
        ("Mobile :", phone),
    ):
        s.text(LEFT + 16, label)
        s.text(LEFT + 130, value)
        s.y -= 16

    # The photograph box. Empty — we have no photograph of the candidate.
    s.c.rect(449, 617, 115, 129, stroke=1, fill=0)
    s.c.setLineWidth(0.7)
    s.c.line(LEFT + 16, 610, RIGHT - 8, 610)

    s.y = 573
    s.row(["1.  (a) Date of Birth"], _v(f, "date_of_birth"), bold_value=False)
    s.row(["     (b) Age Relaxation claimed"], "NO")
    s.space()

    home_city = _v(f, "home_town")
    district = _v(f, "home_district")
    state = _v(f, "home_state")

    s.row(
        ["2.  (a) Address for correspondence to which", "     Communication is to be sent"],
        "",
        value_on=0,
    )
    s.row(["          Post Office:"])
    s.row(["          City:"], home_city, bold_value=False)
    s.row(["          District:"], district, bold_value=False)
    s.row(["          State :"], state, bold_value=False)
    s.row(["          Pin Code :"], _v(f, "pin_code"), bold_value=False)
    s.row(["     (b) Telephone No. (with STD Code)"], "-")
    s.row(["     (c) Mobile No."], phone, bold_value=False)
    s.row(["     (d) Fax No."])
    s.row(["     (e) E-mail address"], email.upper(), bold_value=False)
    s.row(["     (f) Permanent Postal Address"], "", value_on=0)
    s.row(["          Post Office:"])
    s.row(["          City:"], home_city, bold_value=False)
    s.row(["          District:"], district, bold_value=False)
    s.row(["          State :"], state, bold_value=False)
    s.row(["          Pin Code :"], _v(f, "pin_code"), bold_value=False)
    s.space()

    s.row(["3.  Gender :"], _v(f, "gender"), bold_value=False)
    s.space()
    s.row(["4.  Marital Status :"], _v(f, "marital_status"), bold_value=False)
    s.row(["(If Married, Nationality of spouse)"])
    s.row(["5.  (a) Citizenship :"], "A CITIZEN OF INDIA.(1)")
    s.row(["     (b) Nationality :"], "INDIAN")
    s.space()
    s.row(["6.  Mother tongue :"], _v(f, "mother_tongue") or "OTHERS")
    s.space()
    s.row(["7.  Place of Birth :"], "", gutter=False)
    s.row(["        If born in India:"], "YES")
    s.row(["      Post Office"], home_city, bold_value=False)
    s.row(["      City/Town/Village"], home_city, bold_value=False)


def _page2(s: Sheet, f: dict, year: str) -> None:
    s.row(["      District"], _v(f, "home_district"), bold_value=False)
    s.row(["      State"], _v(f, "home_state"), bold_value=False)
    s.row(["      Pincode"], _v(f, "pin_code"), bold_value=False)
    s.space(10)

    s.row(["8.  (a) Community"], _v(f, "category"), bold_value=False)

    for n, body in (
        (
            "Note 1:",
            "No change in the community status already indicated by candidate in his / her "
            "application form for this examination will be allowed by the Commission except in "
            f"the circumstances mentioned in the Rule 26 of CSE Rules, {year}.",
        ),
        (
            "Note 2:",
            "In case you are a 'SC, ST, OBC(Non Creamy Layer) or EWS' candidate, upload a scanned "
            "copy of certificate in support of your claim. For, SC/ST/OBC(Non Creamy Layer)/EWS "
            "candidates, it should be issued prior to the date of closure of online application "
            f"form for Civil Services (Preliminary) Examination,{year} (i.e. prior to 24.03.{year}).",
        ),
        (
            "Note 3:",
            "'Income and Asset Certificate' based on the income for Financial Year 2019-20 (i.e. "
            "for the period from 1st April, 2019 to 31st March, 2020) must only be submitted to "
            "claim the benefit of the Economically Weaker Section reservation as per the "
            "prescribed format and such candidates must meet the Income and Asset criteria issued "
            "by the Central Government. Certificate of any other Financial Year shall not be "
            "treated as valid.",
        ),
        (
            "Note 4:",
            "In case you are an OBC candidate, OBC(Non-Creamy Layer) certificate based on the "
            "income for the Financial Years (FYs) 2019-2020, 2018-2019 and 2017-2018 must only be "
            "submitted.",
        ),
    ):
        s.text(LEFT, n)
        s.para(body, x=LEFT + 52, indent=0, width=RIGHT - LEFT - 52)

    s.row(["     (b)   Certificate No."])
    s.row(["     (c)   Date of issue"])
    s.row(["     (d)   Designation of issuing authority"])
    s.row(["     (e)   Full address of issuing authority"])
    s.space(14)

    s.row(
        [
            "     (f)   Name of the Caste as mentioned in",
            "            the Community Certificate and",
            "            Name of the issuing State.",
            "            [For SC/ST/OBC Candidates]",
        ],
        _v(f, "category"),
        value_on=0,
        bold_value=False,
    )
    s.row(["     (g)  State Creamy or Non Creamy Layer"])
    s.row(
        [
            "     (h)  If you belong to any of the minority",
            "            Communities notified by the Government",
            "            (Muslim/Christians/Sikhs/Buddhists/",
            "            Zoroastrians[Parsi]/Jains)",
        ],
        "NO",
    )
    s.row(["      (i)  If yes, Name of the Minority", "            community"])
    s.space(12)

    s.row(
        [
            "  9.1.(a)      Whether you are a candidate with",
            "                  Benchmark Disability (upload a",
            "                  scanned Certificate of disability)",
        ],
        "NO",
        value_on=0,
    )
    s.row(["                    If yes, disability certificate form"])
    s.row(["     (b)         Category"])
    s.space(6)
    s.row(
        [
            "     (c)         Percentage of disability as indicated in",
            "                  the Certificate of Disability",
        ],
        value_on=0,
    )
    s.row(["     (d)         Certificate No."])
    s.row(["     (e)         Date of Issue"])
    s.row(["     (f)          Designation of issuing authority"])
    s.row(["     (g)         Full address of issuing authority"])
    s.row(["     (h)         Would you require scribe in the", "                  Examination"], value_on=0)


def _page3(s: Sheet, f: dict, year: str) -> None:
    for n, body in (
        (
            "Note 1:",
            "The Persons with Benchmark Disabilities in the categories of blindness, locomotor "
            "disability (both arm affected – BA) and cerebral palsy will be provided the "
            "facility of scribe, if desired by the person. In case of other category of Persons "
            "with Benchmark Disabilities as defined under section 2(r) of the RPWD Act, 2016, the "
            "facility of scribe will be allowed to such candidates on production of a certificate "
            "to the effect that the person concerned has physical limitation to write, and scribe "
            "is essential to write examination on behalf, from the Chief Medical Officer/ Civil "
            "Surgeon/Medical Superintendent of a Government Health Care institution as per "
            f"proforma at Appendix – IV of the Notice of CSE, {year} dated 4th March, {year}.",
        ),
        (
            "Note 2:",
            "The candidates have discretion of opting for his/her own scribe or request the "
            "Commission for the same.",
        ),
        (
            "Note 3:",
            "The qualification of the Commission’s scribe as well as own scribe will not be "
            "more than the minimum qualification criteria of the examination. However, the "
            "qualification of the scribe should always be matriculate or above.",
        ),
        (
            "Note 4:",
            "The Persons with Benchmark Disabilities in the category of blindness, locomotor "
            "disability (both arm affected – BA) and cerebral palsy will be allowed "
            "Compensatory Time of twenty minutes per hour of the examination. In case of other "
            "categories of Persons with Benchmark Disabilities, this facility will be provided on "
            "production of a certificate to the effect that the person concerned has physical "
            "limitation to write from the Chief Medical Officer/ Civil Surgeon/ Medical "
            "Superintendent of a Government Health Care institution as per proforma at Appendix "
            f"– IV of the Notice of CSE, {year} dated 4th March, {year}.",
        ),
    ):
        s.text(LEFT, n)
        s.para(body, x=LEFT + 52, width=RIGHT - LEFT - 52)

    s.row(
        ['  (h)(i)     If yes, "Commission\'s Scribe" or "Own', '                 Scribe"'],
        value_on=0,
    )
    s.row(
        [
            "     (i)        Are you a person with Locomotor",
            "                 Disability and Cerebral Palsy and",
            "                 having impairment in Dominant",
            "                 Writing Extremity",
        ],
        value_on=0,
    )
    s.row(["     (j)        Would you require any assistive", "                 device(s)"], value_on=0)
    s.row(
        ["     (k)        Would you require question paper in", "                 larger font size?"],
        value_on=0,
    )
    s.space(20)

    s.text(LEFT, "Note: Larger font is only for PwBD Candidates suffering from Blindness/ Low Vision.", bold=True)
    s.y -= LEADING + 8

    s.row(
        [
            "  9. 2. (a)  Have you ever been recommended as a",
            "                  PwBD candidate in the examinations",
            "                  conducted by the UPSC in the past?",
        ],
        "NO",
        value_on=0,
    )
    s.space(6)
    s.text(LEFT, "(b). If yes, mention name and year of the examination(s) with Roll No.")
    s.y -= LEADING + 2
    s.grid(
        PWBD_COLS,
        [("Name of the Examination", "Year of the Examination", "Roll No.")],
        centre_cols=(),
    )
    s.space(10)

    s.row(
        [
            "     (c)        Whether such recommendation was on",
            "                 the basis of the Certificate of Disability",
            "                 NOW UPLOADED by you for the",
            f"                 CS(M) Exam, {year}?",
        ],
        "NO",
        value_on=0,
    )
    s.row(
        [
            "     (d)        After any such recommendation by the",
            "                 UPSC were you ever found UNFIT/",
            "                 NOT RECOMMENDED by the Central",
            "                 Standing Medical Board or any other",
            "                 Medical Board constituted by the",
            "                 Government with regard to your",
            "                 physical disability?",
        ],
        "NO",
        value_on=0,
    )
    s.row(["     (e)        If yes, provide details thereof"])


def _page4(s: Sheet, f: dict) -> None:
    s.row(["10.  Choice of Centre for Examination"], _v(f, "exam_centre"))
    s.space(8)
    s.row(
        ["      (a).  Do you want to change your Centre for", "             Main Examination?"],
        "NO",
        value_on=0,
    )
    s.space(14)

    s.row(
        [
            "11.  (a) Do you hail from Arunachal Pradesh/",
            "      Manipur/Meghalaya/Mizoram/Nagaland/",
            "      Sikkim and are claiming exemption",
            "      from appearing in INDIAN LANGUAGE",
            "      FOR PAPER A?",
        ],
        "NO",
    )
    s.row(["   (ii)Indian Language for Paper A"], _v(f, "mother_tongue"))
    s.row(["  (b) Optional Subject for paper VI & VII"], _v(f, "optional_subject"))
    s.space(12)

    s.row(
        [
            "12. (a)Language Medium for Examination",
            "      for Paper I to Paper V",
            "      (Essay and General Studies)",
        ],
        _v(f, "medium_of_instruction") or "ENGLISH",
    )
    s.space(10)
    s.row(
        [
            "   (b) Language Medium for Examination",
            "      for Paper VI to Paper VII (Optional",
            "      Subject as at (b) of Col. 11 above)",
        ],
        _v(f, "medium_of_instruction") or "ENGLISH",
    )
    s.space(10)
    s.row(
        [
            "   (c) In case of Sindhi and Santhali",
            "      type of script should be indicated",
            "      by the candidate",
        ],
    )
    s.space(10)
    s.row(
        [
            "   (d)Language Medium for Interview",
            "         Test(i.e. para 27 of the Instructions)",
            "         to the Candidates)",
        ],
        _v(f, "medium_of_instruction") or "ENGLISH",
    )
    s.space(12)

    s.row(["13.  (a) Name of Father"], _v(f, "fathers_name"), bold_value=False)
    s.row(["  (b) Name of Mother"], _v(f, "mothers_name"), bold_value=False)
    s.row(["  (c) Nationality of Father"], "INDIAN")
    s.row(["  (d) Nationality of Mother"], "INDIAN")
    s.row(["  (e) Father's Profession:"], _v(f, "fathers_occupation"))
    s.row(["  (f) Mother's Profession:"], _v(f, "mothers_occupation"))
    s.row(["  (g) If your father is in service, the post held by him"], gutter=False)
    s.row(
        [
            "  (g)(i) if retired indicate the post held",
            "        by him at the time of his retirement,",
            "        otherwise fill 'NOT APPLICABLE'",
        ],
        _v(f, "fathers_post") or "NOT APPLICABLE",
    )
    s.row(["  (h) If your Mother is in service,the post held by her"], gutter=False)
    s.row(
        [
            "  (h)(i) if retired indicate the post held",
            "        by her at the time of her retirement,",
            "        otherwise fill 'NOT APPLICABLE'",
        ],
        _v(f, "mothers_post") or "NOT APPLICABLE",
    )
    s.row(["  (i) Annual income of your Father"])
    s.row(["  (j) Annual income of your Mother"])
    s.row(["  (k) State to which your Father originally", "       belongs"], _v(f, "home_state"), value_on=0)
    s.row(["  (l) District to which your Father originally", "       belongs"], _v(f, "home_district"), value_on=0)
    s.row(["  (m) State to which your Mother originally", "        belongs"], _v(f, "home_state"), value_on=0)


def _page5(s: Sheet, f: dict) -> None:
    city = _v(f, "home_town")
    district = _v(f, "home_district")
    state = _v(f, "home_state")

    s.row(["  (n) District to which your Mother originally", "       belongs"], district, value_on=0)
    s.row(["  (o) Father's present postal Address", "     (If deceased give last address)"], value_on=0)
    s.row(["                Post Office:"], city, bold_value=False)
    s.row(["                City:"], city, bold_value=False)
    s.row(["                District:"], district, bold_value=False)
    s.row(["                State :"], state, bold_value=False)
    s.row(["                Pin Code :"], _v(f, "pin_code"), bold_value=False)
    s.row(["  (p) Mother's present postal Address", "     (If deceased give last address)"], value_on=0)
    s.row(["                Post Office:"], city, bold_value=False)
    s.row(["                City:"], city, bold_value=False)
    s.row(["                District:"], district, bold_value=False)
    s.row(["                State :"], state, bold_value=False)
    s.row(["                Pin Code :"], _v(f, "pin_code"), bold_value=False)
    s.space(14)

    s.row(
        [
            "   (q) Whether your family owns or possesses",
            "     any of the following assets.",
            "     i. 5 acres of agricultural land and above;",
            "     ii. Residential flat of 1000 sq ft. and above;",
            "     iii. Residential plot of 100 sq. yards and",
            "     above in notified municipalities;",
            "     iv. Residential, plot of 200 sq. yards and",
            "     above in areas other than the notified",
            "     municipalities.",
        ],
    )
    s.space(14)

    s.row(
        [
            "14.1(a) Do you possess the prescribed Educational",
            "  Qualification (Vide rule-6 of the rules of the Examination)?",
            "  Please upload a scanned copy of the Certificate",
            '  if the answer is "YES"',
        ],
        "YES",
    )
    s.row(["    (b)   Certificate No."])
    s.row(["    (c)   Date of issue"])
    s.row(["    (d)   Designation of issuing authority"])
    s.row(["    (e)   Full address of issuing authority"])
    s.space(18)

    s.para(
        "Note : If you do not possess the prescribed educational qualification as mentioned in "
        "rule-6 of the examination your candidature is liable to be cancelled. The proof of "
        "passing the requisite examination should be dated earlier than the due date (closing "
        "date) of Detailed Application Form-I of the Civil Services (Main) Examination."
    )
    s.space(14)

    s.row(
        [
            "  (f)(i) Do you have any basic Educational",
            "   Qualification or higher qualification",
            "   obtained from a foreign institution?",
        ],
        "NO",
    )
    s.space(2 * LEADING)

    # The heading sits at the foot of page 5 on the reference and its table
    # opens page 6.
    s.para(
        "14.2 Educational Qualifications : Commencing with Matriculation or equivalent "
        "examination till Graduation:-"
    )
    s.text(LEFT, "(Please upload scanned copy of all Certificates/Degree)")


def _page6(s: Sheet, f: dict, year: str) -> None:
    header = (
        "Examination Passed",
        "Class/ Division /Grade",
        "Percentage of Marks(%)",
        "CGPA Score",
        "Out of",
        "Year of Passing",
        "Subject(s)",
        "Name of School/College /Institution",
        "Name of Board/University",
    )
    stream = _v(f, "graduation_subject")
    rows = [
        header,
        (
            "10th or Equivalent",
            _v(f, "tenth_grade"),
            "",
            "",
            "",
            _v(f, "tenth_year"),
            "",
            _v(f, "tenth_school"),
            _v(f, "tenth_board"),
        ),
        (
            "12th or Equivalent",
            _v(f, "twelfth_grade"),
            "",
            "",
            "",
            _v(f, "twelfth_year"),
            "",
            _v(f, "twelfth_school"),
            _v(f, "twelfth_board"),
        ),
    ]
    s.grid(EDU_COLS, rows, bold_rows=(1, 2))

    # The stream banner spans the whole table, exactly as it does on the form.
    s.grid((sum(EDU_COLS),), [(f"Stream at Graduation Level :--      {stream}",)], bold_rows=(0,))

    s.grid(
        EDU_COLS,
        [
            (
                _v(f, "graduation_degree") or "GRADUATION",
                _v(f, "grad_grade"),
                "",
                "",
                "",
                _v(f, "grad_year"),
                _v(f, "graduation_subject"),
                _v(f, "graduation_college"),
                _v(f, "university") or _v(f, "graduation_college"),
            )
        ],
        bold_rows=(0,),
    )
    s.space(22)

    employed = "YES" if str(f.get("current_employment") or f.get("work_experience") or "").strip() else "NO"
    s.row(["15.(i)  Have you ever been employed? :"], employed)
    s.space(18)
    s.row(
        [
            "16.   Have you ever been debarred by",
            "         the UPSC from any of its",
            "         Examinations/Selections?",
        ],
        "NO",
    )
    s.space(28)

    previous = [p.strip() for p in str(f.get("previous_attempts") or "").split(",") if p.strip()]
    s.row(
        [
            "17.   Whether you have ever applied for",
            "        U.P.S.C. Examination /Recruitment:-",
        ],
        "YES" if previous else "NO",
    )
    s.text(LEFT + 14, "Details of other application for Examination/Recruitment held/to be held by UPSC :-")
    s.y -= LEADING + 2

    applied = [
        (
            "Name of Examination/Post",
            "Month and year of Examination /Advt. No./Item No. for Recruitment",
            "Roll. No.",
            "Whether you appeared at the Examination",
            "Whether you appeared at the Interview",
            "Whether you were recommended for appointment",
            "Whether you joined/appointed",
            "Whether continuing till date or resigned(with date)",
        )
    ]
    for entry in previous:
        applied.append((entry.upper(), "", "", "YES", "", "NO", "NO", "NA"))
    s.grid(APPLIED_COLS, applied, bold_rows=tuple(range(1, len(applied))))
    s.space(16)

    s.row(
        [
            "18(a).   How many times have you appeared",
            "            at the Civil Services(Pre) Examination",
            "            so far, including the current",
            f"            Examination held in October, {year}",
        ],
        str(f.get("attempt_number") or "1"),
    )
    s.space(8)
    s.text(LEFT, f"18(b).     Details of Examination in which you have appeared including CS(P), {year}")
    s.y -= LEADING + 4
    years = [p for p in previous if p.strip()][:3]
    s.grid(
        (55.2, 60.0, 60.0, 60.0),
        [("Year", *(years + [""] * 3)[:3])],
        x=160.8,
        centre_cols=(),
    )


def _page7(s: Sheet, f: dict, year: str) -> None:
    s.grid(
        (57.6, 55.2, 60.0, 57.6),
        [("Roll No.", _v(f, "roll_number"), "", "")],
        x=160.8,
        centre_cols=(),
    )
    s.space(24)

    s.row(
        [
            "19. Have you ever accepted allocation",
            "      to a Service/Post on the basis",
            "      of Civil Services Examination",
            "      held in earlier years?",
        ],
        "NO",
    )
    s.row(
        [
            "(a).  Year of the Civil Services",
            "       Examination on the basis of which",
            "       you had been last allocated to",
            "        service/post",
        ],
    )
    s.row(["(b).  Name of service/post to which", "        allocated"])
    s.row(["(c).  Your Roll No. for the examination"])
    s.row(["(d).  Whether you were appointed/joined", "       Service?"])
    s.space(10)
    s.row(["(e).  Whether you are continuing in that", "       Service/Post?"])
    s.space(10)
    s.row(
        [
            "(f).  If you have resigned from such post/service",
            "Mention date of acceptance of the resignation",
            " by the Competent authority",
        ],
    )
    s.space(20)

    s.text(LEFT, "20. Fee Payment Details (Subject to Verification)   ")
    s.text(LEFT + 268, ":-", bold=True)
    s.y -= LEADING
    s.row(["      Application No."])
    s.row(["      Transaction-Id"])
    s.row(["      Paid (in Rs.)"])
    s.row(["      Agency Name"])
    s.row(["      Mode of Payment"])
    s.space(12)

    s.para(
        "Details of Fee paid:Candidates applying (excepting Female/SC/ST/PwBD candidates who are "
        "exempted from payment of fee) for Civil Services (Main) Examination are required to pay "
        "a fee of Rs.200/- (Rupees Two Hundred only) either by depositing the money in any Branch "
        "of SBI by cash, or by using Net Banking facility of SBI or by using Visa/Master/Rupay "
        "Credit/Debit card."
    )
    s.space(20)

    s.text(LEFT, "21. Photo-ID Proof")
    s.text(LEFT + 106, "|")
    s.y -= LEADING
    s.space(20)

    s.text(LEFT, "22.  List of Scanned documents uploaded by the candidate:-")
    s.y -= LEADING
    for item in (
        "--> Scanned Copy of proof of date of birth as prescribed in Para below Note IV under "
        "Rule 5 of the rules for the exam. [Col. 1(a) of this form]",
        "--> Scanned Copy of Certificate in support of claim to belong to SC / ST / OBC (Non "
        "Creamy Layer)/EWS (details of which have been indicated in Col.8),  UNDERTAKING FOR "
        "OBC/EWS CANDIDATES, as applicable",
        "--> Scanned Copy of the certificate of graduation or equivalence educational "
        "qualifications (including a copy of recognition letter / equivalence certificate from "
        "AIC/UGC, if applicable)[Col. 14 of this form]",
        "--> Copy of the selected Photo ID Proof (viz. Aadhaar Card, Voter Card, PAN Card, "
        "Passport, Driving Licence or any other Photo ID Proof issued by the Central/State "
        "Government.)",
    ):
        s.para(item, x=LEFT + 18, width=RIGHT - LEFT - 18)


def _page8(s: Sheet, f: dict, year: str) -> None:
    s.y = PAGE_H - 58
    s.centre("DECLARATION BY THE CANDIDATE", size=13)
    s.space(14)

    s.para(
        "I, hereby declare that all statements and entries made in all the columns of this "
        "application are true, complete and correct to the best of my knowledge and belief.",
        x=LEFT + 100,
        width=RIGHT - LEFT - 110,
    )
    s.space(10)

    for clause in (
        "2. That I have read Rule 19 of the Rules of the Civil Services Examination, "
        f"{year} published in Part I – Section 1 of the Gazette of India Extraordinary dated "
        f"4th March, {year} and understand that in the event of any information being found false "
        "or incorrect or ineligibility being detected before or after the examination, or "
        "flouting of any instructions given by the Commission alongwith e-Admit card/ Question "
        "– cum – Answer Booklets/ e-Summon letter etc.action can be taken against me by "
        "the Commission.",
        "3. That I further declare that I fulfil all the eligibility conditions regarding age "
        "limits, educational qualifications etc. prescribed for admission to the Examination.  I "
        "have not exhausted the number of attempts admissible to me under the Rule 3 of the Rules "
        f"of the Examination, {year}.",
        "4. That I have not withheld any information required as per this Detailed Application "
        "Form- I.",
        "5. I have thoroughly scrutinised the list of scanned documents as enumerated in Column 21 "
        "and 22 of the DAF-I and uploaded scanned copies of all the documents relevant for me.",
        "6. That I have read the Rules of Examination and the instructions carefully and I hereby "
        "undertake to abide by them.",
        "7. That I have informed my Head of the Office/Department in writing that I have applied "
        "for this examination as required in Col. 15 (i) of the DAF-I.",
    ):
        s.para(clause, x=LEFT + 100, indent=4, width=RIGHT - LEFT - 110)
        s.space(10)

    s.space(30)
    s.c.rect(RIGHT - 220, s.y - 8, 160, 84, stroke=1, fill=0)
    s.y -= 26
    s.c.setFont(BODY, SIZE)
    s.c.drawCentredString(RIGHT - 140, s.y, "Signature of the Candidate")
    s.y -= 40

    s.para(
        "[Note: Online submission of the DAF-I by the candidate within prescribed time period is "
        "construed as his/her signed applicaion]",
        x=LEFT + 106,
        width=RIGHT - LEFT - 130,
        bold=True,
    )
