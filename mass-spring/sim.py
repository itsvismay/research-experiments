#import numpy
import autograd
import autograd.numpy as numpy

from scipy import optimize

import pickle

from viz import render

def construct_P_matrices(springs, n_points, d):
    return numpy.array([
        numpy.concatenate((
            numpy.concatenate((numpy.zeros((d, d * s_k[0])), numpy.identity(d), numpy.zeros((d, d * n_points - d * (s_k[0] + 1)))), axis=1),
            numpy.concatenate((numpy.zeros((d, d * s_k[1])), numpy.identity(d), numpy.zeros((d, d * n_points - d * (s_k[1] + 1)))), axis=1),
        )) for s_k in springs])

def main():
    ### Setup

    # Constants
    d = 2  # dimensions
    I = numpy.identity(d)
    B = numpy.concatenate((I, -I), axis=1)  # Difference matrix

    # Simulation Parameters
    spring_const = 10.0 # Technically could vary per spring
    h = 0.005
    mass = 0.05
    # Initial conditions
    starting_stretch = 1#0.6

    # starting_points = numpy.array([
    #     [0.4, 0.5],
    #     [0.6, 0.5],
    #     [0.8, 0.5],
    #     [1, 0.5]
    # ])
    starting_points = numpy.array([
        [0,1],
        [0,0],
        [1,1],
        [1,0],
        [2,1],
        [2,0],
        [3,1],
        [3,0],
        [4,1],
        [4,0],
    ]) * 0.1 + 0.3
    n_points = len(starting_points) # Num points
    q_initial = starting_points.flatten()

    pinned_points = numpy.array([0, 1])
    q_mask = numpy.ones(n_points * d, dtype=bool)
    q_mask[numpy.concatenate([pinned_points * d + i for i in range(d)])] = False

    springs = [
        (0, 2),
        (0, 3),
        (2, 3),
        (1, 2),
        (1, 3),
        (2, 4),
        (2, 3),
        (2, 5),
        (3, 5),
        (3, 4),
        (4, 5),
        (4, 6),
        (4, 7),
        (5, 6),
        (5, 7),
        (6, 7),

        (6, 8),
        (6, 9),
        (7, 8),
        (7, 9),
        (8, 9),
    ]

    n_springs = len(springs)
    P_matrices = construct_P_matrices(springs, n_points, d)
    
    all_spring_offsets = (B @ (P_matrices @ q_initial).T).T
    rest_lens = numpy.linalg.norm(all_spring_offsets, axis=1) * starting_stretch

    mass_matrix = numpy.identity(len(q_initial)) * mass # Mass matrix
    external_forces = numpy.array([0, -9.8] * n_points)

    # Assemble offsets
    P = numpy.concatenate(B @ P_matrices)

    # Assemble forces
    Pf = numpy.array([numpy.zeros(len(springs) * 2)] * n_points * 2)
    for i, s in enumerate(springs):
        n0 = s[0] * 2
        n1 = s[1] * 2
        col = i * 2
        Pf[n0][col] = 1.0
        Pf[n0+1][col+1] = 1.0
        Pf[n1][col] = -1.0
        Pf[n1+1][col+1] = -1.0
   # print(Pf.shape) #?????? why wrong

    def compute_internal_forces(q):
        # forces = numpy.array([[0.0, 0.0]] * len(springs))
        # for i, s in enumerate(springs):
        #     s0 = s[0] * 2
        #     s1 = s[1] * 2
        #     offset_vec = q[s0: s0 + 2] - q[s1: s1 + 2]
        #     length = numpy.linalg.norm(offset_vec)
        #     displacement_dir = offset_vec / length
        #     force = -spring_const * (length / rest_lens[i] - 1.0) * displacement_dir
        #     forces[i] = force

        offsets = (P @ q).reshape(n_springs, 2)
        lengths = numpy.sqrt((offsets * offsets).sum(axis=1))
        #normed_displacements = numpy.linalg.norm(offsets, axis=1)
        normed_displacements = offsets / lengths[:, None]
        forces = (spring_const * (lengths / rest_lens - 1.0))[:, None] * normed_displacements # Forces per spring
        forces = forces.flatten()

        global_forces = Pf @ forces
        return global_forces

    # print(compute_internal_forces(q_initial))
    # print(autograd.jacobian(compute_internal_forces)(q_initial))

    def find_natural_modes():
        # q = q_initial * 2
        # # K = spring_const * numpy.concatenate(B @ P_matrices) * 1.0 / mass # Multiplying by inverse mass to ger rid of mass matrix on right
        # F = (1.0 - (1.0 / rest_lens) * numpy.sqrt(numpy.einsum('ij,ij->i', q.T @ P_matrices.transpose((0,2,1)) @ B.T, (B @ P_matrices @ q))))
        # print(len(q_initial))
        # print(F.shape)
        # print(F)
        # print(len(springs))
        K = autograd.jacobian(compute_internal_forces)(q_initial) * 1.0 / mass
        w, v = numpy.linalg.eig(K)
        print(numpy.real_if_close(w[0]))
        print(v)

        i = 0
        while True:
            render(numpy.real_if_close(v[i] + q_initial), springs, save_frames=False)
            i = (i + 1) % len(v)
            import time
            time.sleep(0.1)
    find_natural_modes()
    exit()

    def kinetic_energy(q_k, q_k1):
        """ Profile this to see if using numpy.dot is different from numpy.matmul (@)"""

        d_q = q_k1 - q_k
        energy = 1.0 / (2 * h ** 2) * d_q.T @ mass_matrix @ d_q

        return energy

    def potential_energy(q_k, q_k1):
        q_tilde = 0.5 * (q_k + q_k1)

        # sum = 0.0
        # for i in range(len(rest_lens)): # TODO I might be able to do this simply with @ (see all_spring_offsets)
        #     P_i = P_matrices[i]
        #     l_i = rest_lens[i]

        #     d_q_tilde_i_sq = q_tilde.T @ P_i.T @ B.T @ B @ P_i @ q_tilde
        #     sum += (1.0 - 1.0 / l_i * numpy.sqrt(d_q_tilde_i_sq)) ** 2

        # Optimized but ugly version
        sum = numpy.sum(
            (1.0 - (1.0 / rest_lens) * numpy.sqrt(numpy.einsum('ij,ij->i', q_tilde.T @ P_matrices.transpose((0,2,1)) @ B.T, (B @ P_matrices @ q_tilde)))) ** 2
        )

        return 0.5 * spring_const * sum

    def discrete_lagrangian(q_k, q_k1):
        return kinetic_energy(q_k, q_k1) - potential_energy(q_k, q_k1)

    D1_Ld = autograd.grad(discrete_lagrangian, 0)  # (q_t, q_t+1) -> R^N*d
    D2_Ld = autograd.grad(discrete_lagrangian, 1)  # (q_t-1, q_t) -> R^N*d


    # Want D1_Ld + D2_Ld = 0
    # Do root finding
    def DEL(new_q, cur_q, prev_q):
        # SUPER hacky way of adding constrained points
        for i in pinned_points:
            new_q = numpy.insert(new_q, i*d, q_initial[i*d])
            new_q = numpy.insert(new_q, i*d+1, q_initial[i*d+1])

        res = D1_Ld(cur_q, new_q) + D2_Ld(prev_q, cur_q) + mass_matrix @ external_forces

        # SUPER hacky way of adding constrained points
        return res[q_mask]

    jac_DEL = autograd.jacobian(DEL, 0)

    def DEL_objective(new_q, cur_q, prev_q):
        res = DEL(new_q, cur_q, prev_q)

        return res.T @ res

    ### Simulation
    q_history = []
    save_freq = 1000
    current_frame = 0
    output_path = 'configurations'

    prev_q = q_initial
    cur_q = q_initial
    while True:
        # SUPER hacky
        constrained_q = cur_q[q_mask]

        sol = optimize.root(DEL, constrained_q, method='broyden1', args=(cur_q, prev_q))#, jac=jac_DEL) # Note numerical jacobian seems much faster
        #sol = optimize.minimize(DEL_objective, constrained_q, args=(cur_q, prev_q), method='L-BFGS-B')#, options={'gtol': 1e-6, 'eps': 1e-06, 'disp': False})
        prev_q = cur_q
        cur_q = sol.x

        # SUPER hacky way of adding constrained points
        for i in pinned_points:
            cur_q = numpy.insert(cur_q, i*d, q_initial[i*d])
            cur_q = numpy.insert(cur_q, i*d+1, q_initial[i*d+1])

        render(cur_q, springs, save_frames=False)

        if save_freq > 0:
            current_frame += 1
            q_history.append(cur_q)

            if current_frame % save_freq == 0:
                with open(output_path, 'wb') as f:
                    pickle.dump(q_history, f)

if __name__ == '__main__':
    main()
