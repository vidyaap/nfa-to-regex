import copy
import simplify
import to_goldbar
import argparse
import ast
import sys
import json


class Exp:
    def __init__(self, name):
        self.exp_type = "Exp"
        self.name = name

    def __str__(self):
        return "Exp(" + str(self.name) + ")"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return hash(str(self)) == hash(str(other))


class Or(Exp):
    # exps is a list (can be more than 2 elements) of everything being OR-ed
    def __init__(self, exps):
        self.exp_type = "Or"
        self.name = "or"
        self.exps = exps

    def __str__(self):
        return "Or(" + str(self.exps) + ")"

    def __repr__(self):
        return str(self)


class Then(Exp):
    # exps is a list (can be more than 2 elements) of everything being THEN-ed
    def __init__(self, exps):
        self.exp_type = "Then"
        self.name = "then"
        self.exps = exps

    def __str__(self):
        return "Then(" + str(self.exps) + ")"

    def __repr__(self):
        return str(self)


class ZeroOrMore(Exp):
    # exp is an Exp type that is being ZM-ed
    def __init__(self, exp):
        self.exp_type = "ZeroOrMore"
        self.name = "zero-or-more"
        self.exp = exp

    def __str__(self):
        return "ZeroOrMore(" + str(self.exp) + ")"

    def __repr__(self):
        return str(self)


class OneOrMore(Exp):
    # exp is an Exp type that is being OM-ed
    def __init__(self, exp):
        self.exp_type = "OneOrMore"
        self.name = "one-or-more"
        self.exp = exp

    def __str__(self):
        return "OneOrMore(" + str(self.exp) + ")"

    def __repr__(self):
        return str(self)


class ZeroOrOne(Exp):
    # exp is an Exp type that is being ZO-ed
    def __init__(self, exp):
        self.exp_type = "ZeroOrOne"
        self.name = "zero-or-one"
        self.exp = exp

    def __str__(self):
        return "ZeroOrOne(" + str(self.exp) + ")"

    def __repr__(self):
        return str(self)


class DFA:
    def __init__(self, states, init_state, final_states, transition_funct):
        self.states = states  # would be each node in the graph
        self.init_state = init_state  # start node
        self.final_states = final_states  # accept nodes (list)
        # dictionary of the form {node1: {node1:"how to get to node1 from node1", node2: "how to get to node2 from node1", ...}, node2:{}, ...}
        self.transition_funct = transition_funct
        self.regex = ''  # the resulting regex that will be returned
        self.ds = {}  # holds the states after collapsing edges
        self.transition_dict = {}  # same as transition_funct but with strings converted to Exps
        self.set_transition_dict()  # fills in transition_dict with info from transition_funct

    def format_nested(self, exp_type, parts):
        if len(parts) == 0:
            return Exp("")
        elif len(parts) == 1:
            return parts[0]
        else:
            return exp_type(parts[0], self.format_nested(exp_type, parts[1:]))

    def set_transition_dict(self):
        dict_states = {r: {c: Exp('_') for c in self.states} for r in self.states}
        for key in self.transition_funct:
            val = self.transition_funct[key]
            for v_key in val:
                if val[v_key] != "_":
                    parts = val[v_key].split(", ")
                    if len(parts) == 1:
                        dict_states[key][v_key] = Exp(val[v_key])
                    else:
                        for i in range(len(parts)):
                            parts[i] = Exp(parts[i])
                        dict_states[key][v_key] = Or(parts)

        self.ds = dict_states
        self.transition_dict = copy.deepcopy(dict_states)

    def get_intermediate_states(self):
        return [state for state in self.states if state not in ([self.init_state] + self.final_states)]

    def get_predecessors(self, state):
        return [key for key, value in self.ds.items() if
                state in value.keys() and value[state].name != '_' and key != state]

    def get_successors(self, state):
        return [key for key, value in self.ds[state].items() if value.name != '_' and key != state]

    def get_if_loop(self, state):
        if self.ds[state][state].name != '_':
            return self.ds[state][state]
        else:
            return Exp("_")

    # creates a ZeroOrMore object
    def format_zero_or_more(self, loop):
        if loop.name != "_" and len(loop.name) > 0:
            return ZeroOrMore(loop)
        else:
            return loop

    # creates a OneOrMore object
    def format_one_or_more(self, loop):
        if loop.name != "_" and len(loop.name) > 0:
            return OneOrMore(loop)
        else:
            return loop

    # checks if a pair of expressions can form a one-or-more
    def check_one_more(self, pred_to_inter, inter_loop):
        if pred_to_inter.name == inter_loop.name:
            return True
        else:
            return False

    # formats path to remove epsilons
    def format_new_path(self, path_parts):
        non_blanks = []
        for x in path_parts:
            # if a part is an epsilon or non-entry
            if len(x.name) != 0 and x.name != "e" and x.name != "_":
                non_blanks += [x]

        # if no parts, return epsilon
        if len(non_blanks) == 0:
            return Exp("e")
        # if one part, return that part
        elif len(non_blanks) == 1:
            return non_blanks[0]
        # if multiple, return THEN of all parts
        else:
            then_list = []
            for part in non_blanks:
                if part.exp_type == "Then":
                    then_list += part.exps
                else:
                    then_list += [part]

            new_path = Then(then_list)
            return new_path

    # formats the expression that goes into the state dictionary
    # combine correctly with existing path at (i, j)
    def format_entry(self, entry, i, j, exp):
        if entry.name == "_" or len(entry.name) == 0:
            return exp
        else:
            if i == j:
                return Or([ZeroOrMore(entry), exp])
            else:
                return Or([entry, exp])

    def toregex(self):
        intermediate_states = self.get_intermediate_states()  # returns everything except for start and accept nodes
        dict_states = self.ds

        for inter in intermediate_states:
            predecessors = self.get_predecessors(inter)  # direct parents of this node
            successors = self.get_successors(inter)  # direct children of this node

            for i in predecessors:
                for j in successors:
                    # returns if there is currently any path found from this node back to itself
                    inter_loop = self.get_if_loop(inter)
                    # if there is a loop found from the current parent to itself, this becomes a ZM
                    pred_loop = self.format_zero_or_more(self.get_if_loop(i))

                    # get the paths from the parent to the current and the current to the child node
                    pred_to_inter = dict_states[i][inter]
                    inter_to_succ = dict_states[inter][j]

                    # based on ZM of parent and loop in current, check for OM
                    if self.check_one_more(pred_to_inter, inter_loop):
                        inter_loop = self.format_one_or_more(inter_loop)
                        new_path = self.format_new_path([pred_loop, inter_loop, inter_to_succ])
                    else:
                        inter_loop = self.format_zero_or_more(inter_loop)
                        pred_to_inter = pred_to_inter
                        new_path = self.format_new_path([pred_loop, pred_to_inter, inter_loop, inter_to_succ])

                    # enter new path from parent to child that doesn't include the current "inter" node
                    dict_states[i][j] = self.format_entry(dict_states[i][j], i, j, new_path)
            # remove inter node
            dict_states = {r: {c: v for c, v in val.items() if c != inter} for r, val in dict_states.items() if
                           r != inter}
            self.ds = copy.deepcopy(dict_states)

        return dict_states[self.init_state][self.final_states[0]]


def main():
    states = []
    init_state = ""
    final_states = []
    transition_funct = {}

    # EXAMPLE (one-or-more(cds)):
    states = ["n1", "n2"]
    init_state = "n1"
    final_states = ["n2"]
    transition_funct = {"n1": {"n1": "_", "n2": "cds"}, "n2": {"n1": "e", "n2": "_"}}

    # to read from STDIN
    # for line in sys.stdin:
    #     args = json.loads(line)
    #     states = args['states']
    #     init_state = args['root']
    #     final_states = args['accepts']
    #     transition_funct = args['transition']

    # create a start node with an empty edge to the actual first edge ('e' is the epsilon)
    start_array = {}
    for key in transition_funct:
        val = transition_funct[key]
        if key == init_state:
            start_array[key] = 'e'
        else:
            start_array[key] = '_'
        val['START'] = '_'
        transition_funct[key] = val
    start_array['FINAL'] = '_'
    transition_funct['START'] = start_array

    # create a final node with an empty edge pointing to it from the actual final node ('e' is the epsilon)
    final_array = {}
    for key in transition_funct:
        val = transition_funct[key]
        if key in final_states:
            val['FINAL'] = 'e'
        else:
            val['FINAL'] = '_'
        final_array[key] = '_'
        transition_funct[key] = val
    final_array['FINAL'] = '_'
    transition_funct['FINAL'] = final_array

    # redefine the initial and final states and the state list
    init_state = 'START'
    final_states = ['FINAL']
    states += ['START', 'FINAL']

    r = Exp("")
    simp = Exp("")
    goldbar = ""

    for f in final_states:
        dfa = DFA(states, init_state, [f], transition_funct)
        r = dfa.toregex()
        simp = simplify.simplify_regex(r)
        goldbar = to_goldbar.to_goldbar(simp)

    print(goldbar)

    # TO RETURN TO JS CODE
    # message = {"goldbar": goldbar}
    # print(json.dumps(message))


# return message


if __name__ == '__main__':
    main()
