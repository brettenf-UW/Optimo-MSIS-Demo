"""
Simple script to test if Gurobi is working correctly.
"""
try:
    import gurobipy as gp
    from gurobipy import GRB
    
    print("Gurobi is installed correctly!")
    
    # Create a simple optimization model
    try:
        # Create a new model
        m = gp.Model("simple")
        
        # Create variables
        x = m.addVar(vtype=GRB.BINARY, name="x")
        y = m.addVar(vtype=GRB.BINARY, name="y")
        z = m.addVar(vtype=GRB.BINARY, name="z")
        
        # Set objective
        m.setObjective(x + y + 2 * z, GRB.MAXIMIZE)
        
        # Add constraint
        m.addConstr(x + 2 * y + 3 * z <= 4, "c0")
        
        # Optimize model
        m.optimize()
        
        print("\nOptimization result:")
        print(f"Objective value: {m.objVal}")
        for v in m.getVars():
            print(f"{v.varName}: {v.x}")
            
        print("\nGurobi license is working correctly!")
        
    except gp.GurobiError as e:
        print(f"Gurobi error: {e}")
except ImportError:
    print("Gurobi is not installed or properly configured.")
    print("Please install Gurobi and set up the license.")