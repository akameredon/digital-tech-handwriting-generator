"""
NERDC 2025 Digital Technologies Scheme of Work
Hard-coded official curriculum for SSS1, SSS2, SSS3.
This is the single source of truth for all lesson note generation.
"""

from typing import Dict, List, Any

NERDC_DIGITAL_TECHNOLOGIES: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "SS1": {
        "First Term": [
            {"week": 1, "topic": "Introduction to Digital Technologies", "content": "Meaning, scope, relevance in modern society"},
            {"week": 2, "topic": "History & Evolution of Digital Technologies", "content": "From abacus to AI; generations of computers"},
            {"week": 3, "topic": "Number Systems", "content": "Binary, decimal, octal, hexadecimal and conversions"},
            {"week": 4, "topic": "Computer Hardware", "content": "Input/output devices, storage, system vs peripheral devices"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment of Weeks 1-4"},
            {"week": 6, "topic": "Computer Software", "content": "System software, application software, utility programs"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Operating Systems", "content": "Functions, types, examples"},
            {"week": 9, "topic": "Computer Maintenance & Safety", "content": "Preventive care, health & safety measures"},
            {"week": 10, "topic": "Data Representation", "content": "Bits, bytes, ASCII, Unicode, images, sound"},
            {"week": 11, "topic": "Revision", "content": "Review of all topics covered"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
        "Second Term": [
            {"week": 1, "topic": "Computer Networks", "content": "LAN, WAN, MAN; components of networks"},
            {"week": 2, "topic": "Internet Technologies", "content": "Internet services, search engines, browsers"},
            {"week": 3, "topic": "Email & Online Communication", "content": "Email etiquette, instant messaging, conferencing"},
            {"week": 4, "topic": "Digital Storage & Cloud Computing", "content": "Types of storage, advantages of cloud, data backup"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment of Weeks 1-4"},
            {"week": 6, "topic": "Cybersecurity I", "content": "Meaning, importance, threats (malware, phishing, hacking)"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Cybersecurity II", "content": "Protection methods - antivirus, firewalls, strong passwords"},
            {"week": 9, "topic": "Data Privacy & Digital Ethics", "content": "Responsible use, cyberbullying, data protection laws"},
            {"week": 10, "topic": "Social Media Technologies", "content": "Benefits, risks, responsible digital citizenship"},
            {"week": 11, "topic": "Revision", "content": "Review of term topics"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
        "Third Term": [
            {"week": 1, "topic": "Word Processing Applications", "content": "Microsoft Word/Google Docs: features, formatting"},
            {"week": 2, "topic": "Spreadsheet Applications I", "content": "Introduction, basic formulas, cell referencing"},
            {"week": 3, "topic": "Spreadsheet Applications II", "content": "Functions, charts, data analysis"},
            {"week": 4, "topic": "Presentation Software", "content": "PowerPoint/Google Slides: slide creation, animations"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment of Weeks 1-4"},
            {"week": 6, "topic": "Database Introduction", "content": "Concept of database, DBMS, tables, records, fields"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Practical Database Management", "content": "Creating simple databases, queries, reports"},
            {"week": 9, "topic": "Emerging Technologies I", "content": "Artificial Intelligence, Internet of Things"},
            {"week": 10, "topic": "Emerging Technologies II", "content": "Robotics, Virtual Reality, Augmented Reality"},
            {"week": 11, "topic": "Revision", "content": "Review of all topics"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
    },
    "SS2": {
        "First Term": [
            {"week": 1, "topic": "Review of SS1 Work", "content": "Quick revision of digital foundations"},
            {"week": 2, "topic": "Advanced Word Processing", "content": "Mail merge, macros, templates"},
            {"week": 3, "topic": "Advanced Spreadsheet I", "content": "Pivot tables, advanced formulas"},
            {"week": 4, "topic": "Advanced Spreadsheet II", "content": "Financial models, scenario analysis"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment"},
            {"week": 6, "topic": "Advanced Presentation Tools", "content": "Multimedia integration, professional designs"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Web Design I", "content": "Introduction to HTML, CSS"},
            {"week": 9, "topic": "Web Design II", "content": "Creating simple websites"},
            {"week": 10, "topic": "Web Publishing & Hosting", "content": "Domains, hosting, publishing process"},
            {"week": 11, "topic": "Revision", "content": "Review of topics"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
        "Second Term": [
            {"week": 1, "topic": "Computer Programming I", "content": "Introduction to algorithms, flowcharts"},
            {"week": 2, "topic": "Computer Programming II", "content": "Introduction to Python/JavaScript"},
            {"week": 3, "topic": "Programming Basics", "content": "Variables, data types, operators"},
            {"week": 4, "topic": "Control Structures", "content": "If-else, loops, functions"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment"},
            {"week": 6, "topic": "Data Science Basics", "content": "Data collection, storage, cleaning"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Big Data & Analytics", "content": "Meaning, applications, tools"},
            {"week": 9, "topic": "Artificial Intelligence", "content": "Applications in education, health, business"},
            {"week": 10, "topic": "Machine Learning Basics", "content": "Concept, simple applications"},
            {"week": 11, "topic": "Revision", "content": "Review of topics"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
        "Third Term": [
            {"week": 1, "topic": "Mobile Application Development I", "content": "Introduction to mobile apps"},
            {"week": 2, "topic": "Mobile Application Development II", "content": "Creating simple Android/iOS apps"},
            {"week": 3, "topic": "Cloud Computing II", "content": "SaaS, PaaS, IaaS"},
            {"week": 4, "topic": "Blockchain Technology", "content": "Concept, cryptocurrency, uses beyond finance"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment"},
            {"week": 6, "topic": "Cybersecurity III", "content": "Ethical hacking, penetration testing"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Cyber Laws & Digital Rights", "content": "Nigerian cybercrime act, global cyber laws"},
            {"week": 9, "topic": "Digital Entrepreneurship", "content": "E-commerce, freelancing, online business"},
            {"week": 10, "topic": "Project Work", "content": "Students develop mini ICT projects"},
            {"week": 11, "topic": "Revision", "content": "Review of topics"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
    },
    "SS3": {
        "First Term": [
            {"week": 1, "topic": "Review of SS2 Work", "content": "Key concepts revision"},
            {"week": 2, "topic": "Advanced Programming I", "content": "Functions, arrays/lists"},
            {"week": 3, "topic": "Advanced Programming II", "content": "Object-Oriented Programming basics"},
            {"week": 4, "topic": "Software Development Life Cycle (SDLC)", "content": "Phases, models (waterfall, agile)"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment"},
            {"week": 6, "topic": "Networking II", "content": "IP addressing, subnetting, protocols"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Cloud & Virtualization", "content": "Virtual machines, remote servers"},
            {"week": 9, "topic": "Internet of Things (IoT) Applications", "content": "Smart homes, smart cities"},
            {"week": 10, "topic": "Data Protection & Backup Systems", "content": "Disaster recovery, redundancy"},
            {"week": 11, "topic": "Revision", "content": "Review of topics"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
        "Second Term": [
            {"week": 1, "topic": "Advanced Web Design", "content": "JavaScript interactivity, responsive design"},
            {"week": 2, "topic": "Advanced Database Management", "content": "SQL basics, queries, reports"},
            {"week": 3, "topic": "Networking III", "content": "Network security, VPNs"},
            {"week": 4, "topic": "Digital Project Management", "content": "Tools (Trello, MS Project), teamwork"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment"},
            {"week": 6, "topic": "Emerging Tech III", "content": "Quantum computing, nanotechnology"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "Revision of SSCE Past Questions I", "content": "Theory + practical"},
            {"week": 9, "topic": "Revision of SSCE Past Questions II", "content": "Case studies, applied ICT"},
            {"week": 10, "topic": "Mock Exam Prep", "content": "Preparation for external examinations"},
            {"week": 11, "topic": "Revision", "content": "Final review"},
            {"week": 12, "topic": "Examination", "content": "End of Term Assessment"},
            {"week": 13, "topic": "Closing", "content": "Term ends"},
        ],
        "Third Term": [
            {"week": 1, "topic": "Comprehensive Revision of SS1-SS3", "content": "Overview of major areas"},
            {"week": 2, "topic": "Past Question Drills (WAEC/NECO)", "content": "Theory, objective"},
            {"week": 3, "topic": "Practical Project I", "content": "Building website/app/database"},
            {"week": 4, "topic": "Practical Project II", "content": "Cybersecurity simulation, IoT demo"},
            {"week": 5, "topic": "Midterm Test", "content": "Assessment"},
            {"week": 6, "topic": "Mock Examination", "content": "Full mock"},
            {"week": 7, "topic": "Midterm Break", "content": "Holiday/Rest"},
            {"week": 8, "topic": "SSCE Preparation", "content": "Exam-focused review"},
            {"week": 9, "topic": "WAEC/NECO & Final Examinations", "content": "External examinations"},
            {"week": 10, "topic": "WAEC/NECO & Final Examinations", "content": "External examinations"},
            {"week": 11, "topic": "Closing & Graduation", "content": "End of senior secondary"},
            {"week": 12, "topic": "Closing & Graduation", "content": "End of senior secondary"},
            {"week": 13, "topic": "Closing & Graduation", "content": "End of senior secondary"},
        ],
    },
}


def get_lesson(class_level: str, term: str, week: int) -> Dict[str, Any] | None:
    """Retrieve a specific weekly topic from the official scheme."""
    try:
        for item in NERDC_DIGITAL_TECHNOLOGIES[class_level][term]:
            if item["week"] == week:
                return item
    except KeyError:
        return None
    return None


def list_all_topics(class_level: str = None) -> List[Dict[str, Any]]:
    """Return a flat list of all topics, optionally filtered by class."""
    results = []
    levels = [class_level] if class_level else ["SS1", "SS2", "SS3"]
    for level in levels:
        for term, weeks in NERDC_DIGITAL_TECHNOLOGIES[level].items():
            for item in weeks:
                results.append({
                    "class": level,
                    "term": term,
                    **item
                })
    return results
