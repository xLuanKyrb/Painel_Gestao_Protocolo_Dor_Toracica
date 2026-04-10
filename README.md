# Painel de Monitoramento - Protocolo de Dor Torácica (ECG)

## Sobre o Projeto
O **Painel de Monitoramento ECG** é um sistema de gestão de tempo real focado no fluxo de atendimento de emergência cardiológica. Desenvolvido para atuar em Unidades de Pronto Atendimento, o sistema digitaliza o acompanhamento do "Protocolo de Dor Torácica", garantindo que os tempos-alvo (SLA) para eletrocardiogramas, exames de troponina e medicação sejam rigorosamente cumpridos.

Este projeto visa reduzir o tempo porta-ECG, otimizar a comunicação entre a triagem e a equipe médica, e garantir total rastreabilidade (auditoria) dos atendimentos para fins médico-legais.

---

## Principais Funcionalidades

* **Painel Dinâmico (Modo TV):** Acompanhamento em tempo real do status de cada paciente, com alertas visuais (cores) e piscantes para procedimentos em atraso.
* **Cálculo Automático de Prazos (SLA):** O sistema calcula automaticamente os horários-alvo com base na hora zero da triagem (Ex: ECG em 10 min, Troponina em 25 min).
* **Gestão de Múltiplas Rotas:** Suporte para até 3 ciclos completos de reavaliação médica (Rotas de Protocolo).
* **Prontuário Médico-Legal (PDF):** Geração de relatório individual detalhado em formato PDF, pronto para assinatura e anexação ao prontuário físico.
* **Auditoria de Acesso (LGPD):** Sistema de logs invisível que registra *quem* fez *o quê* e *quando*, garantindo a segurança da informação.
* **Backup Automático (Scheduled Jobs):** Rotina autônoma de backup diário do banco de dados para prevenção de perda de dados hospitalares.
* **Exportação Gerencial:** Módulo de extração de relatórios completos em formato Excel (.xlsx) para auditoria e estatísticas da coordenação.

---

## Tecnologias e Arquitetura

O sistema foi focada em resistência e baixa necessidade de manutenção de infraestrutura:

* **Backend:** Python 3 com framework Flask.
* **Servidor de Produção (WSGI):** Waitress (otimizado para processamento paralelo em ambientes de alta demanda).
* **Banco de Dados:** SQLite3 (local e criptografável, sem dependência de serviços externos).
* **Tarefas em Segundo Plano:** APScheduler (para as rotinas de backup noturno).
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla) e Bootstrap 5 (para responsividade e interface limpa).
* **Exportações:** Biblioteca SheetJS (para Excel) e impressão nativa formatada em PDF.

---

## Como Executar o Projeto Localmente

### Pré-requisitos
* Python 3.8 ou superior instalado.
* Acesso ao terminal (CMD, PowerShell ou VS Code).

### Passo a Passo

1. **Clone o repositório ou extraia os arquivos:**
   ```bash
   git clone https://github.com/xLuanKyrb/painel_dor_toracica.git
   cd ecg
