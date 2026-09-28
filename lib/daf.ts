/**
 * The Detailed Application Form, shared between entry and review.
 *
 * Both screens must agree on the field list, which fields are required, and
 * how the form becomes an API payload — so all three live here rather than
 * being duplicated and drifting.
 */

export type DafForm = Record<string, string>;

export const EMPTY: DafForm = {
  full_name: "", gender: "", marital_status: "", category: "",
  date_of_birth: "", fathers_occupation: "", mothers_occupation: "",
  home_state: "", home_district: "", home_town: "", mother_tongue: "",
  languages_known: "",
  graduation_subject: "", graduation_college: "", university: "",
  post_graduation: "", medium_of_instruction: "English",
  tenth_board: "", tenth_year: "", tenth_grade: "",
  twelfth_board: "", twelfth_year: "", twelfth_grade: "",
  grad_year: "", grad_grade: "",
  optional_subject: "", service_preference: "", cadre_preference: "",
  attempt_number: "1", previous_attempts: "", exam_centre: "",
  hobbies: "", sports_and_achievements: "", positions: "",
  prizes_and_medals: "", extracurricular: "",
  work_experience: "", current_employment: "",
};

export const SPECIMEN: DafForm = {
  ...EMPTY,
  full_name: "Preetam Kumar", gender: "Male", marital_status: "Single",
  category: "General", fathers_occupation: "Government service",
  mothers_occupation: "Homemaker",
  home_state: "Rajasthan", home_district: "Jaipur", home_town: "Sikar",
  mother_tongue: "Hindi", languages_known: "Hindi, English, Marwari",
  graduation_subject: "Mechanical Engineering", graduation_college: "MNIT Jaipur",
  tenth_board: "CBSE", tenth_year: "2013", tenth_grade: "First, 92%",
  twelfth_board: "CBSE", twelfth_year: "2015", twelfth_grade: "First, 88%",
  grad_year: "2019", grad_grade: "First",
  optional_subject: "Mathematics", service_preference: "IAS, IPS, IFS",
  attempt_number: "4", previous_attempts: "CSE 2020, 2021, 2022",
  exam_centre: "Jaipur",
  hobbies: "Chess, Reading historical fiction",
  sports_and_achievements: "District-level chess",
  positions: "NSS unit secretary",
  prizes_and_medals: "State chess bronze",
  extracurricular: "NCC B certificate",
  work_experience: "Two years, PWD Rajasthan",
  current_employment: "Assistant Engineer, PWD",
};

export const list = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);

/** Field labels, grouped exactly as the real DAF groups them. */
export const SECTIONS: {
  title: string;
  hint: string;
  fields: { key: string; label: string; placeholder?: string; note?: string; wide?: boolean }[];
}[] = [
  {
    title: "Personal",
    hint: "Who the Chairman is addressing, and what your family background opens up.",
    fields: [
      { key: "full_name", label: "Full name", placeholder: "As on your application" },
      { key: "date_of_birth", label: "Date of birth", placeholder: "DD/MM/YYYY" },
      { key: "gender", label: "Gender", placeholder: "Male / Female" },
      { key: "marital_status", label: "Marital status", placeholder: "Single / Married" },
      { key: "category", label: "Category", placeholder: "General / OBC / SC / ST / EWS" },
      {
        key: "fathers_occupation", label: "Father's occupation",
        placeholder: "Government service",
        note: "Boards mine this hard — a police father invites questions on police reform.",
      },
      { key: "mothers_occupation", label: "Mother's occupation", placeholder: "Homemaker" },
    ],
  },
  {
    title: "Home",
    hint: "Your permanent home, not your postal address. Expect local questions.",
    fields: [
      { key: "home_state", label: "Home state", placeholder: "Rajasthan" },
      { key: "home_district", label: "Home district", placeholder: "Jaipur" },
      { key: "home_town", label: "Home town or village", placeholder: "Sikar" },
      {
        key: "mother_tongue", label: "Mother tongue", placeholder: "Hindi",
        note: "Expect: which dialect is spoken locally, and where else it is spoken.",
      },
      {
        key: "languages_known", label: "Other languages", placeholder: "English, Marwari",
        note: "Comma separated.", wide: true,
      },
    ],
  },
  {
    title: "Education",
    hint: "The full table. Boards read across it — an inconsistent record is a question.",
    fields: [
      { key: "graduation_subject", label: "Graduation subject", placeholder: "Mechanical Engineering" },
      { key: "graduation_college", label: "College", placeholder: "MNIT Jaipur" },
      { key: "university", label: "University", placeholder: "If different from college" },
      { key: "post_graduation", label: "Post-graduation", placeholder: "If any" },
      { key: "medium_of_instruction", label: "Medium of instruction", placeholder: "English" },
      { key: "tenth_board", label: "10th — board", placeholder: "CBSE" },
      { key: "tenth_year", label: "10th — year", placeholder: "2013" },
      { key: "tenth_grade", label: "10th — division or %", placeholder: "First, 92%" },
      { key: "twelfth_board", label: "12th — board", placeholder: "CBSE" },
      { key: "twelfth_year", label: "12th — year", placeholder: "2015" },
      { key: "twelfth_grade", label: "12th — division or %", placeholder: "First, 88%" },
      { key: "grad_year", label: "Graduation — year", placeholder: "2019" },
      { key: "grad_grade", label: "Graduation — division", placeholder: "First" },
    ],
  },
  {
    title: "Examination",
    hint: "Your optional subject and your record with the Commission so far.",
    fields: [
      {
        key: "optional_subject", label: "Optional subject", placeholder: "Mathematics",
        note: "The subject expert will keep descending until you run out.",
      },
      { key: "attempt_number", label: "Attempt number", placeholder: "4" },
      {
        key: "previous_attempts", label: "Previous attempts", placeholder: "CSE 2020, 2021, 2022",
        note: "“This is your fourth attempt — what changed?” is a standard question.",
      },
      { key: "exam_centre", label: "Examination centre", placeholder: "Jaipur" },
      {
        key: "service_preference", label: "Service preference", placeholder: "IAS, IPS, IFS",
        note: "Comma separated, in your order.", wide: true,
      },
      { key: "cadre_preference", label: "Cadre preference", placeholder: "Rajasthan, UP", wide: true },
    ],
  },
  {
    title: "Personality and record",
    hint: "The psychologist's material. Expect to be asked to demonstrate, not describe.",
    fields: [
      {
        key: "hobbies", label: "Hobbies", placeholder: "Chess, Reading historical fiction",
        note: "If you write, you will be asked to recite. If you read, for the last book.",
        wide: true,
      },
      { key: "sports_and_achievements", label: "Sports", placeholder: "District-level chess", wide: true },
      { key: "positions", label: "Positions of responsibility", placeholder: "NSS unit secretary", wide: true },
      { key: "prizes_and_medals", label: "Prizes and medals", placeholder: "State chess bronze", wide: true },
      { key: "extracurricular", label: "Extra-curricular", placeholder: "NCC B certificate", wide: true },
      { key: "work_experience", label: "Work experience", placeholder: "Two years, PWD Rajasthan", wide: true },
      { key: "current_employment", label: "Currently employed as", placeholder: "Assistant Engineer, PWD", wide: true },
    ],
  },
];

export const REQUIRED = new Set([
  "full_name", "home_state", "home_district",
  "graduation_subject", "graduation_college",
  "optional_subject", "hobbies", "service_preference",
]);

/** Builds the API payload. Kept beside the field list so the two cannot drift. */
export function dafPayload(form: DafForm) {
  return {
    full_name: form.full_name,
    date_of_birth: form.date_of_birth,
    gender: form.gender,
    marital_status: form.marital_status,
    category: form.category,
    fathers_occupation: form.fathers_occupation,
    mothers_occupation: form.mothers_occupation,
    home_state: form.home_state,
    home_district: form.home_district,
    home_town: form.home_town,
    mother_tongue: form.mother_tongue,
    languages_known: list(form.languages_known),
    education: {
      graduation_subject: form.graduation_subject,
      graduation_college: form.graduation_college,
      university: form.university,
      post_graduation: form.post_graduation,
      medium_of_instruction: form.medium_of_instruction || "English",
      tenth: { board_or_university: form.tenth_board, year_of_passing: form.tenth_year, division_or_grade: form.tenth_grade },
      twelfth: { board_or_university: form.twelfth_board, year_of_passing: form.twelfth_year, division_or_grade: form.twelfth_grade },
      graduation: { board_or_university: form.university, year_of_passing: form.grad_year, division_or_grade: form.grad_grade },
    },
    optional_subject: form.optional_subject,
    hobbies: list(form.hobbies),
    sports_and_achievements: list(form.sports_and_achievements),
    positions_of_responsibility: list(form.positions),
    prizes_and_medals: list(form.prizes_and_medals),
    extracurricular: list(form.extracurricular),
    work_experience: list(form.work_experience),
    current_employment: form.current_employment,
    service_preference: list(form.service_preference),
    cadre_preference: list(form.cadre_preference),
    attempt_number: Number(form.attempt_number) || 1,
    previous_attempts: form.previous_attempts,
    exam_centre: form.exam_centre,
  };
}

const DRAFT_KEY = "panelmind.daf.draft";

export interface DafDraft {
  form: DafForm;
  /** Upload needs a louder "check this" than typing does. */
  fromUpload: boolean;
  /**
   * What the PDF actually said, label by label, in the form's own words.
   *
   * The review shows this rather than our 30-field schema. A real DAF carries
   * around 194 fields; mapping them into 30 slots invents blanks that were
   * never missing from the aspirant's form, and hides everything the board
   * would actually question on.
   */
  rawFields?: Record<string, string>;
}

export function stashDafDraft(draft: DafDraft): void {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

/** Reads without clearing, so refresh and back both survive. */
export function readDafDraft(): DafDraft | null {
  const raw = typeof window === "undefined" ? null : sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as DafDraft;
  } catch {
    return null;
  }
}

export function clearDafDraft(): void {
  sessionStorage.removeItem(DRAFT_KEY);
}

/**
 * Maps a parsed upload onto form fields, returning only what was actually
 * read. Spread over the current form so a blank in the scan never wipes
 * something the aspirant already typed.
 */
export function formFromUpload(d: Record<string, unknown>): DafForm {
  const e = (d.education ?? {}) as Record<string, unknown>;
  const str = (v: unknown) => (typeof v === "string" ? v : "");
  const joined = (v: unknown) => (Array.isArray(v) ? v.join(", ") : "");

  const candidate: DafForm = {
    full_name: str(d.full_name),
    date_of_birth: str(d.date_of_birth),
    fathers_occupation: str(d.fathers_occupation),
    home_state: str(d.home_state),
    home_district: str(d.home_district),
    mother_tongue: str(d.mother_tongue),
    languages_known: joined(d.languages_known),
    graduation_subject: str(e.graduation_subject ?? d.graduation_subject),
    graduation_college: str(e.graduation_college ?? d.graduation_college),
    university: str(e.university ?? d.university),
    post_graduation: str(e.post_graduation ?? d.post_graduation),
    optional_subject: str(d.optional_subject),
    hobbies: joined(d.hobbies),
    service_preference: joined(d.service_preference),
    cadre_preference: joined(d.cadre_preference),
    work_experience: joined(d.work_experience),
    attempt_number: d.attempt_number == null ? "" : String(d.attempt_number),
  };

  // Empties are dropped, so every remaining value is a string.
  return Object.fromEntries(
    Object.entries(candidate).filter(([, v]) => v !== ""),
  ) as DafForm;
}

/**
 * The inverse of `dafPayload`: turn a stored DAF back into form fields.
 *
 * Used to resume — an aspirant picks up a previous attempt and the board is
 * convened from the same file. Deliberately exhaustive rather than reusing
 * `formFromUpload`, which maps only the subset an OCR pass can find; resuming
 * through that would silently drop everything typed by hand.
 */
export function formFromDaf(daf: Record<string, unknown>): DafForm {
  const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
  const joined = (v: unknown) => (Array.isArray(v) ? v.join(", ") : "");
  const e = (daf.education ?? {}) as Record<string, unknown>;
  const level = (k: string) => (e[k] ?? {}) as Record<string, unknown>;

  const out: DafForm = {
    full_name: str(daf.full_name),
    gender: str(daf.gender),
    marital_status: str(daf.marital_status),
    category: str(daf.category),
    date_of_birth: str(daf.date_of_birth),
    fathers_occupation: str(daf.fathers_occupation),
    mothers_occupation: str(daf.mothers_occupation),
    home_state: str(daf.home_state),
    home_district: str(daf.home_district),
    home_town: str(daf.home_town),
    mother_tongue: str(daf.mother_tongue),
    languages_known: joined(daf.languages_known),
    graduation_subject: str(e.graduation_subject),
    graduation_college: str(e.graduation_college),
    university: str(e.university),
    post_graduation: str(e.post_graduation),
    medium_of_instruction: str(e.medium_of_instruction),
    tenth_board: str(level("tenth").board_or_university),
    tenth_year: str(level("tenth").year_of_passing),
    tenth_grade: str(level("tenth").division_or_grade),
    twelfth_board: str(level("twelfth").board_or_university),
    twelfth_year: str(level("twelfth").year_of_passing),
    twelfth_grade: str(level("twelfth").division_or_grade),
    grad_year: str(level("graduation").year_of_passing),
    grad_grade: str(level("graduation").division_or_grade),
    optional_subject: str(daf.optional_subject),
    service_preference: joined(daf.service_preference),
    cadre_preference: joined(daf.cadre_preference),
    attempt_number: str(daf.attempt_number) || "1",
    previous_attempts: str(daf.previous_attempts),
    exam_centre: str(daf.exam_centre),
    hobbies: joined(daf.hobbies),
    sports_and_achievements: joined(daf.sports_and_achievements),
    positions: joined(daf.positions_of_responsibility),
    prizes_and_medals: joined(daf.prizes_and_medals),
    extracurricular: joined(daf.extracurricular),
    work_experience: joined(daf.work_experience),
    current_employment: str(daf.current_employment),
  };

  return { ...EMPTY, ...out };
}
