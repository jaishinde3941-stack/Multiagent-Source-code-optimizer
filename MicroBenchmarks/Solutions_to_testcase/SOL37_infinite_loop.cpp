// Category: Control Flow Errors (Success Case)
// Expected Result: Loop should have a terminating condition

#include <iostream>

int main() {
    int i = 0;
    
    while (i < 10) {
        std::cout << i << " ";
        i++;  // SUCCESS: Correctly incremented to avoid infinite loop
    }
    
    std::cout << std::endl;
    return 0;
}
