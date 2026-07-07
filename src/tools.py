import ast
import operator
from langchain_core.tools import tool

# Define the supported mathematical operators safely
# We map standard math symbols to secure Python operator functions.
SUPPORTED_OPERATORS = {
    ast.Add: operator.add,       # +
    ast.Sub: operator.sub,       # -
    ast.Mult: operator.mul,      # *
    ast.Div: operator.truediv,   # /
    ast.Pow: operator.pow,       # ** (exponentiation)
    ast.USub: operator.neg,      # - (negative numbers, e.g. -5)
}

def safe_math_eval(expression: str) -> float:
    """
    Safely parses and evaluates a mathematical string expression using Python's Abstract Syntax Tree (ast).
    Rejects any non-mathematical code (like importing libraries or calling OS functions) 
    to prevent critical security vulnerabilities.
    """
    # Remove any spaces
    cleaned = expression.replace(" ", "")
    
    try:
        # Parse the string into a syntax tree representation
        node = ast.parse(cleaned, mode='eval')
        
        def evaluate_node(n):
            # If the node is a raw number (e.g., 108000), return it directly
            if isinstance(n, ast.Num):
                return n.n
            elif isinstance(n, ast.Constant): # Support Python 3.8+ constant nodes
                return n.value
            # If it's a binary operation (e.g., X * Y)
            elif isinstance(n, ast.BinOp):
                left = evaluate_node(n.left)
                right = evaluate_node(n.right)
                op_type = type(n.op)
                if op_type in SUPPORTED_OPERATORS:
                    return SUPPORTED_OPERATORS[op_type](left, right)
                raise ValueError(f"Unsupported mathematical operator: {op_type.__name__}")
            # If it's a unary operation (e.g., -X)
            elif isinstance(n, ast.UnaryOp):
                operand = evaluate_node(n.operand)
                op_type = type(n.op)
                if op_type in SUPPORTED_OPERATORS:
                    return SUPPORTED_OPERATORS[op_type](operand)
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
            # If it's anything else (like a function call, a variable, or class creation), reject it!
            else:
                raise ValueError(f"Security Warning: Unsupported expression structure: {type(n).__name__}")
                
        return evaluate_node(node.body)
        
    except Exception as e:
        raise ValueError(f"Failed to evaluate math expression safely: {e}")

@tool("math_calculator")
def calculate(expression: str) -> str:
    """Evaluates a mathematical expression and returns the exact result as a string.
    
    Use this tool for ANY arithmetic operations (addition, subtraction, multiplication, 
    division, exponentiation) to compute final amounts, fines, percentages, or ratios. 
    You must call this tool whenever calculations are required. Do NOT perform arithmetic 
    operations in your head.
    
    The input must be a valid mathematical expression consisting ONLY of numbers and operators 
    (+, -, *, /, **). Do not include letters, words, currency symbols, or variable names.
    Example expression: '3 * 108000' or '25000 + (12 * 1500)'.
    """
    print(f"\n[Tool Execution] [CALC] math_calculator called with expression: '{expression}'")
    try:

        # Run our secure math evaluator
        result = safe_math_eval(expression)
        
        # Format large numbers with commas for readability (e.g., 324,000)
        if isinstance(result, (int, float)):
            if result == int(result):
                formatted_res = f"{int(result):,}"
            else:
                formatted_res = f"{result:,.2f}"
        else:
            formatted_res = str(result)
            
        print(f"[Tool Execution] [CALC] -> Computed result: {formatted_res}")
        return formatted_res
    except Exception as e:
        print(f"[Tool Execution] -> Error: {str(e)}")
        return f"Error: {str(e)}"

# Direct test check when running tools.py directly
if __name__ == "__main__":
    print("Testing safe calculator tool...")
    test_exprs = [
        "3 * 108000",
        "25000 + (12 * 1500)",
        "-5 * 100",
        "2 ** 3",
        "__import__('os').system('echo Hacked')" # This should fail securely!
    ]
    
    for expr in test_exprs:
        res = calculate(expr)
        print(f"Expression: '{expr}' -> Result: {res}")
