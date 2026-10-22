"""
desktop/subplugins/office/content.py
------------------------------------
Authoritative, maintainable content registry for Microsoft Office automation.
Contains predefined texts and datasets for Word, PowerPoint, and Excel:
- INITIAL_WORD_TEXT: Exact introductory text for Word document initialization
- SYNAPTIMESH_WORD_TEXT: Exact SynaptiMesh BCI integration text for Word insertion
- POWERPOINT_SLIDES: 5 predefined Python-domain presentation slides
- POWERPOINT_TECHNICAL_APPROACH: Predefined Technical Approach slide for EDIT
- SHEET1_STOCK_DATA: Stock price dataset (21 rows, 5 columns)
- SHEET2_DEGREE_DATA: Degree & career dataset (21 rows, 5 columns)
"""

# ===========================================================================
# 1. MICROSOFT WORD PREDEFINED TEXTS (EXACT SPECIFICATION)
# ===========================================================================

INITIAL_WORD_TEXT = """Introduction to Quantum Computing and Interactive Learning

Quantum computing is an emerging field of computation that uses principles of quantum mechanics to process information. Unlike classical computers, which represent information using bits with values of zero or one, quantum computers use quantum bits, commonly called qubits. Qubits can exist in superposition states, and multiple qubits can exhibit entanglement. These properties enable quantum systems to represent and process information in ways that differ from conventional computing.

Quantum algorithms are designed to exploit these properties for specific computational problems. Examples include Grover's search algorithm, which provides a quadratic query advantage for unstructured search, and Shor's algorithm, which demonstrates how quantum computation could factor integers efficiently relative to known classical methods. However, practical quantum computers remain limited by noise, hardware constraints, and error rates.

Learning quantum computing requires an understanding of linear algebra, probability, complex numbers, quantum states, and quantum gates. Students must also understand how circuits are constructed, how algorithms transform quantum states, and how measurements produce classical outcomes.

An interactive quantum-learning platform can make these concepts easier to explore. Instead of relying exclusively on theoretical explanations, learners can construct quantum circuits, configure gates, execute algorithms, and examine simulation results. Visual representations of state transformations and measurement probabilities can help connect mathematical principles with computational behavior.

A well-designed learning platform can also integrate different simulation engines through clearly defined interfaces. This enables learners to compare execution behavior and understand the differences between simulation environments without changing the fundamental structure of their learning activities.

Modular software architecture further improves maintainability. Separating the client interface from server-side execution allows presentation, algorithm processing, simulation, and result handling to evolve independently. A plugin-based architecture can organize these capabilities into reusable components that are loaded and invoked according to supported tasks.

Ultimately, interactive quantum education aims to make a complex technical subject more accessible through experimentation, visualization, and structured learning. By combining mathematical foundations, executable circuits, and clear result interpretation, such platforms can help learners develop a deeper understanding of quantum algorithms and their potential applications."""


SYNAPTIMESH_WORD_TEXT = """SynaptiMesh: Non-Invasive Brain–Computer Interface Integration

SynaptiMesh is a project concept focused on integrating non-invasive brain–computer interface (BCI) technology with software applications to support hands-free computer interaction. The objective is to explore how brain-signal interpretation can be connected to a modular software system that converts recognized commands into meaningful digital actions.

A non-invasive BCI obtains brain-related signals using sensors positioned outside the body, commonly through electroencephalography (EEG). These signals contain patterns that can be analyzed to identify particular mental states or trained command classes. Since EEG measurements are affected by noise, movement, sensor placement, and individual differences, reliable command recognition requires appropriate signal processing, validation, and confidence assessment.

The proposed SynaptiMesh workflow consists of signal acquisition, preprocessing, feature extraction, classification, command validation, application routing, and action execution. Each stage has a distinct responsibility. The signal-processing stage prepares incoming measurements, while the classification stage interprets the extracted features. The command-management layer validates recognized commands before forwarding them to the appropriate application or automation service.

A central objective is to provide a controlled interface between BCI-generated commands and computer applications. Rather than allowing raw classifier output to trigger arbitrary actions, the system can map validated commands to a predefined set of supported operations. This approach improves predictability and provides a clear boundary between signal interpretation and application execution.

A command-based interaction model can represent actions such as PUSH, PULL, LEFT, and RIGHT. The meaning of each command depends on the current application and interaction state. For example, a command may select an application at one stage and perform an application-specific operation at another. A state manager and command registry can help ensure that commands are interpreted in the correct context.

The software architecture can be organized into independent client and server components. The client manages the user interface and presents execution feedback, while the server handles command validation, routing, and supported automation operations. A plugin architecture can organize application-specific capabilities into reusable modules. This structure allows new applications to be integrated without placing every application workflow inside the central command manager.

Microsoft Word automation provides one possible application-level use case. Validated BCI commands could be mapped to operations such as creating a document, inserting predefined content, saving a file, and deleting selected text. Destructive operations should be constrained to the intended selection, while file-saving operations should handle destination prompts and errors safely.

Reliability remains an important consideration because non-invasive BCI classification is not always perfectly accurate. Confidence thresholds, rejection of uncertain commands, command deduplication, explicit application state, and clear execution feedback can reduce unintended actions. Sensitive operations should include appropriate safeguards, and automation failures should be reported rather than treated as successful executions.

SynaptiMesh therefore provides a framework for exploring the connection between non-invasive neural interfaces and modular desktop automation. Its broader potential lies in making computer interaction more accessible while maintaining predictable command interpretation, controlled execution, and clear separation between signal processing and application logic. Actual performance and usability must be established through testing with the selected BCI hardware, signal-processing methods, and supported applications."""


# ===========================================================================
# 2. POWERPOINT PREDEFINED SLIDE CONTENT (EXACT SPECIFICATION)
# ===========================================================================

POWERPOINT_BCI_TITLE = {
    "title": "SynaptiMesh – BCI Automation Project",
    "subtitle": "Non-Invasive Brain-Computer Interface Input & Desktop Automation Integration",
}

# 5 Predefined Python-Domain Slides for LEFT sequence cycling
POWERPOINT_PYTHON_DOMAIN_SLIDES = [
    {
        "index": 1,
        "title": "Python Domain – Desktop Automation",
        "topic": "Python Domain in SynaptiMesh",
        "bullets": [
            "Role of Python Domain: Core desktop application automation layer for the SynaptiMesh BCI internship.",
            "Desktop-Side Focus: Connects neural command inputs to native Windows application execution.",
            "BCI Command Processing: Translates normalized directional commands (PUSH, PULL, LEFT, RIGHT) into digital actions.",
            "Targeted Execution: Maps validated commands directly to application-specific automation handlers.",
            "Reusable Architecture: Modular handlers engineered for reliable, reproducible desktop operations.",
        ],
    },
    {
        "index": 2,
        "title": "Application Automation in the Python Domain",
        "topic": "Applications Automated",
        "bullets": [
            "Supported Applications: Google Chrome, Gmail, YouTube, Notepad.",
            "Microsoft Office Suite: Word, Excel, PowerPoint unified under desktop automation.",
            "Common Interface: Centralized dashboard provides unified access to all supported desktop applications.",
            "Scope Accuracy: Focuses on supported automation workflows for each integrated application.",
            "Platform Native: Leverages COM automation for Office and native APIs for system tools.",
        ],
    },
    {
        "index": 3,
        "title": "Unified Application Integration",
        "topic": "Unified Control Architecture",
        "bullets": [
            "Centralized Python Dashboard: Single control interface across all supported desktop applications.",
            "Common BCI Command Interface: Consistent directional navigation and intent execution.",
            "Application-Specific Mapping: Context-aware command resolution based on active application state.",
            "Intelligent Routing: Capability router forwards validated commands to the appropriate handler.",
            "Consistent Execution Feedback: Verifiable status reporting (SUCCESS, FAILED, REJECTED) across apps.",
        ],
    },
    {
        "index": 4,
        "title": "Python Agent and Executable Packaging",
        "topic": "Python Agent Executable",
        "bullets": [
            "Windows Executable Packaging: Packaged as standalone Windows .exe using PyInstaller.",
            "Simplified Startup: Direct execution without manual Python environment configuration.",
            "Intended Server Communication: Maintains WebSocket and HTTP telemetry with the SynaptiMesh server.",
            "Task Execution: Performs supported Python-domain desktop automation tasks reliably.",
            "Deployment Efficiency: Streamlines client installation across varied Windows workstations.",
        ],
    },
    {
        "index": 5,
        "title": "Deployment and Future Scope",
        "topic": "Deployment and Evolution",
        "bullets": [
            "Startup Workflow: Launch server runtime and connected Python automation agent.",
            "Communication Setup: Configures local WebSocket and REST API channels.",
            "Distribution: Packaged executable deployment for end-user assistive workstations.",
            "Command Validation: Real-time verification of supported application operations and safety limits.",
            "Telemetry & Error Handling: Proactive failure monitoring, state logging, and session recovery.",
            "Future Scope: Extending automation to additional assistive desktop tasks and productivity workflows.",
        ],
    },
]

# Fixed Technical Approach Slide for PUSH + RIGHT (EDIT)
POWERPOINT_TECHNICAL_APPROACH = {
    "title": "Technical Approach",
    "bullets": [
        "BCI Input — Receive the supported BCI command combination.",
        "Command Processing — Validate and interpret the incoming command.",
        "Application Mapping — Resolve the requested operation in the PowerPoint context.",
        "Automation Execution — Execute the requested presentation operation through the existing automation handler.",
        "Result Handling — Track execution status and handle failures.",
        "Deployment — Use the packaged Python agent where required by the existing architecture.",
    ],
}


# ===========================================================================
# 3. MICROSOFT EXCEL DATASETS (EXACT SPECIFICATION)
# ===========================================================================

SHEET1_STOCK_HEADERS = ["Company", "Symbol", "Current Price", "Change", "Market Cap"]

SHEET1_STOCK_DATA = [
    ["Apple Inc.", "AAPL", "$182.52", "+1.25%", "$2.85T"],
    ["Microsoft Corp.", "MSFT", "$415.28", "+0.84%", "$3.09T"],
    ["NVIDIA Corp.", "NVDA", "$124.50", "+3.18%", "$3.06T"],
    ["Alphabet Inc.", "GOOGL", "$176.40", "-0.42%", "$2.20T"],
    ["Amazon.com Inc.", "AMZN", "$186.40", "+1.10%", "$1.94T"],
    ["Meta Platforms Inc.", "META", "$502.60", "+2.35%", "$1.27T"],
    ["Tesla Inc.", "TSLA", "$248.80", "-1.85%", "$792.4B"],
    ["Berkshire Hathaway", "BRK.A", "$645,200", "+0.15%", "$930.1B"],
    ["Eli Lilly and Co.", "LLY", "$948.30", "+1.45%", "$901.2B"],
    ["Broadcom Inc.", "AVGO", "$162.80", "+2.04%", "$760.5B"],
    ["JPMorgan Chase & Co.", "JPM", "$210.45", "-0.30%", "$602.8B"],
    ["Visa Inc.", "V", "$274.15", "+0.55%", "$558.4B"],
    ["Walmart Inc.", "WMT", "$68.70", "+0.92%", "$552.1B"],
    ["Exxon Mobil Corp.", "XOM", "$116.30", "-1.10%", "$462.7B"],
    ["Mastercard Inc.", "MA", "$458.20", "+0.60%", "$428.9B"],
    ["Procter & Gamble Co.", "PG", "$168.90", "+0.35%", "$398.2B"],
    ["Home Depot Inc.", "HD", "$364.50", "-0.20%", "$361.8B"],
    ["Costco Wholesale", "COST", "$846.10", "+1.15%", "$375.4B"],
    ["Merck & Co. Inc.", "MRK", "$122.40", "-0.65%", "$310.2B"],
    ["Chevron Corp.", "CVX", "$148.90", "-0.85%", "$274.6B"],
    ["ASML Holding NV", "ASML", "$832.60", "+1.75%", "$332.8B"],
]


SHEET2_DEGREE_HEADERS = ["Degree", "Field", "Key Skills", "Career Opportunities", "Demand Level"]

SHEET2_DEGREE_DATA = [
    ["B.Tech CSE", "Computer Science", "Programming, DSA, DBMS, OS", "Software Engineer, Full Stack Developer", "Very High"],
    ["B.Tech ECE", "Electronics & Communication", "Embedded Systems, VLSI, Signal Processing", "Embedded Engineer, Hardware Designer", "High"],
    ["B.Tech AI & DS", "Artificial Intelligence & Data", "Machine Learning, Deep Learning, Python", "AI Engineer, Data Scientist, ML Ops", "Very High"],
    ["B.Tech IT", "Information Technology", "Cloud Computing, Networking, Web Tech", "Cloud Engineer, DevOps Specialist", "High"],
    ["B.Tech Robotics", "Robotics & Automation", "ROS, Kinematics, PLC, Microcontrollers", "Robotics Engineer, Automation Architect", "Very High"],
    ["B.Tech Cyber Security", "Information Security", "Network Security, Cryptography, Pen Testing", "Security Analyst, Ethical Hacker", "Very High"],
    ["B.Tech Biomedical", "Biomedical Engineering", "Biomechanics, Bio-instrumentation, Imaging", "Medical Device Engineer, Clinical Tech", "High"],
    ["B.Tech Mechanical", "Mechanical Engineering", "CAD/CAM, Thermodynamics, FEA, SolidWorks", "Design Engineer, Automotive Specialist", "Moderate"],
    ["B.Tech Electrical", "Electrical Engineering", "Power Systems, Control Theory, MATLAB", "Power Engineer, Control Specialist", "High"],
    ["B.Tech Civil", "Civil Engineering", "Structural Analysis, AutoCAD, Geo-tech", "Structural Engineer, Project Lead", "Moderate"],
    ["B.Tech Aerospace", "Aerospace Engineering", "Aerodynamics, Avionics, Propulsion, CFD", "Flight Dynamics Engineer, Avionics Eng", "High"],
    ["B.Tech Mechatronics", "Mechatronics Systems", "Electro-mechanics, Sensors, IoT Firmware", "IoT Developer, Mechatronics Engineer", "High"],
    ["B.Sc Computer Science", "Computing Sciences", "Python, Algorithms, Database Systems", "Software Developer, Technical Support", "High"],
    ["B.Sc Data Analytics", "Data Sciences", "Statistics, R, Python, PowerBI, SQL", "Data Analyst, Business Analyst", "High"],
    ["BCA", "Computer Applications", "Web Dev, Database Management, Java, C++", "Application Programmer, QA Engineer", "Moderate"],
    ["MCA", "Advanced Computer Apps", "Distributed Systems, Cloud Architecture", "Senior Developer, Systems Analyst", "High"],
    ["M.Tech VLSI", "Microelectronics", "Verilog, FPGA, RTL Design, ASIC Flow", "VLSI Design Engineer, Chip Architect", "Very High"],
    ["M.Tech AI & Robotics", "Autonomous Systems", "Deep Learning, SLAM, Sensor Fusion", "Autonomous Systems Dev, AI Researcher", "Very High"],
    ["B.Tech Chemical", "Chemical Engineering", "Process Simulation, Reaction Kinetics", "Process Engineer, Plant Supervisor", "Moderate"],
    ["B.Sc Physics", "Applied Physics", "Optics, Computational Physics, Mechanics", "Optical Engineer, Research Associate", "Moderate"],
    ["M.S. Quantum Tech", "Quantum Information Science", "Quantum Algorithms, Qiskit, Linear Algebra", "Quantum Software Dev, Quantum Analyst", "Emerging High"],
]
