// ============================================================
// Adam-Viz — Définitions des 12 agents ADAM (V2)
// Données uniquement — la scène 3D est dans index.html
// ============================================================

window.ADAM_AGENTS = [
    // 0°  — droite
    { id: 'adam-praetor',  name: 'ADAM-PRAETOR',  emoji: '🛡️', color: '#ff2244', hex: 0xff2244, role: 'Surveillance système',  x: 10.00, z: 0.00, channels: ['config:changed', 'file:created', 'file:modified'] },
    // 30° — haut-droite
    { id: 'adam-sentinel', name: 'ADAM-SENTINEL', emoji: '📡', color: '#00ddff', hex: 0x00ddff, role: 'Veille technologique',   x:  8.66, z: 5.00, channels: ['security:scan', 'security:alert'] },
    // 60° — haut-droite
    { id: 'adam-critic',   name: 'ADAM-CRITIC',   emoji: '🔍', color: '#ffdd00', hex: 0xffdd00, role: 'Audit qualité',          x:  5.00, z: 8.66, channels: ['critic:review', 'deploy:completed'] },
    // 90° — haut
    { id: 'adam-cicd',     name: 'ADAM-CICD',     emoji: '🚀', color: '#ffffff', hex: 0xffffff, role: 'Intégration continue',   x:  0.00, z: 10.00, channels: ['cicd:hook', 'git:push'] },
    // 120° — haut-gauche
    { id: 'adam-backup',   name: 'ADAM-BACKUP',   emoji: '💾', color: '#2244aa', hex: 0x2244aa, role: 'Sauvegarde',             x: -5.00, z: 8.66, channels: ['backup:requested', 'schedule:daily'] },
    // 150° — haut-gauche
    { id: 'adam-deploy',   name: 'ADAM-DEPLOY',   emoji: '📦', color: '#00ff88', hex: 0x00ff88, role: 'Déploiement & restart',  x: -8.66, z: 5.00, channels: ['deploy:requested', 'cicd:completed'] },
    // 180° — gauche
    { id: 'adam-blue',     name: 'ADAM-BLUE',     emoji: '🔵', color: '#4488ff', hex: 0x4488ff, role: 'Sécurité 24/24',         x: -10.00, z: 0.00, channels: ['blue:watch', 'deploy:completed'] },
    // 210° — bas-gauche
    { id: 'adam-docs',     name: 'ADAM-DOCS',     emoji: '📚', color: '#ff8800', hex: 0xff8800, role: 'Documentation',          x: -8.66, z: -5.00, channels: ['wiki:update', 'docs:changed'] },
    // 240° — bas-gauche
    { id: 'adam-monitor',  name: 'ADAM-MONITOR',  emoji: '📊', color: '#44ff44', hex: 0x44ff44, role: 'Monitoring hardware',    x: -5.00, z: -8.66, channels: ['monitor:alert', 'system:health'] },
    // 270° — bas
    { id: 'adam-doctor',   name: 'ADAM-DOCTOR',   emoji: '🩺', color: '#ff66aa', hex: 0xff66aa, role: 'Visite médicale',        x:  0.00, z: -10.00, channels: ['doctor:watch', 'system:health', 'service:restarted'] },
    // 300° — bas-droite
    { id: 'adam-red',      name: 'ADAM-RED',      emoji: '🔴', color: '#ff4444', hex: 0xff4444, role: 'Scan OSINT',             x:  5.00, z: -8.66, channels: ['osint:alert'] },
    // 330° — bas-droite
    { id: 'adam-viz-checker', name: 'ADAM-VIZ-CHECKER', emoji: '👁️', color: '#ddaaff', hex: 0xddaaff, role: 'Vérification dashboards', x: 8.66, z: -5.00, channels: ['dashboard:down'] },
];

window.ADAM_STATIONS = [
    { name: 'Porte Sécurité',    x:  8, z: -6, color: '#ff2244' },
    { name: 'Baie Réseau',       x: -8, z:  0, color: '#00ddff' },
    { name: 'Labo Test',         x:  8, z:  0, color: '#ff66aa' },
    { name: 'Station Doc',       x:  0, z: -6, color: '#ff8800' },
    { name: 'Centre Méditation', x:  0, z:  0, color: '#aa66ff' },
    { name: 'Git Hub',           x: -4, z:  4, color: '#888888' },
    { name: 'Archive',           x:  4, z:  4, color: '#2244aa' },
    { name: 'Pas de Tir',        x:  8, z:  6, color: '#ffffff' },
    { name: 'Serveur Perf',      x:  4, z: -4, color: '#ffdd00' },
    { name: 'Poste de Code',     x: -4, z: -4, color: '#4488ff' },
    { name: 'Entrepôt',          x: -8, z:  6, color: '#00ff88' },
];