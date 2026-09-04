#!/usr/bin/env python3
"""
Script para executar a suite de testes do OperAI.
"""
import sys
import subprocess
import argparse


def run_tests(test_path="tests/", verbose=True, coverage=False, html_report=False):
    """Executa os testes com pytest."""
    cmd = ["pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=app", "--cov-report=term-missing"])
        if html_report:
            cmd.append("--cov-report=html")
    
    cmd.append(test_path)
    
    print(f"Executando: {' '.join(cmd)}")
    print("=" * 70)
    
    result = subprocess.run(cmd, capture_output=False)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Executa testes do OperAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Rodar todos os testes
  python run_tests.py
  
  # Rodar com cobertura
  python run_tests.py --coverage
  
  # Rodar testes específicos
  python run_tests.py tests/test_task_runner.py
  
  # Rodar com relatório HTML
  python run_tests.py --coverage --html
        """
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default="tests/",
        help="Caminho para os testes (padrão: tests/)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=True,
        help="Saída detalhada (padrão: True)"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Gerar relatório de cobertura"
    )
    
    parser.add_argument(
        "--html",
        action="store_true",
        help="Gerar relatório HTML (requer --coverage)"
    )
    
    args = parser.parse_args()
    
    # Valida argumentos
    if args.html and not args.coverage:
        print("Erro: --html requer --coverage")
        sys.exit(1)
    
    # Executa testes
    returncode = run_tests(
        test_path=args.path,
        verbose=args.verbose,
        coverage=args.coverage,
        html_report=args.html
    )
    
    sys.exit(returncode)


if __name__ == "__main__":
    main()
